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

from math import degrees
import random
from io_scene_foundry.utils.nwo_constants import WU_SCALAR
from io_scene_foundry.managed_blam import Tag
import bpy
from io_scene_foundry.utils import nwo_utils
        
def get_light_id_from_data(data):
    rnd = random.Random()
    rnd.seed(data.name)
    return str(rnd.randint(-2147483, 2147483))

class ScenarioStructureLightingInfoTag(Tag):
    tag_ext = 'scenario_structure_lighting_info'
        
    def _read_fields(self):
        self.block_generic_light_definitions = self.tag.SelectField("Block:generic light definitions")
        self.block_generic_light_instances = self.tag.SelectField("Block:generic light instances")
    
    # TODO Write code that builds this tag from blender
    # General ideas:
    # Create lighting defintion id intprop for light data in blender
    # Loop through blender lights and create entries in tag light definitions
    # Create a list of all defintion ids in the tag, if one in blender is not present in the tag, make a new block entry. IDs let us keep track of lights between blender/tag
    # Light instances then built from light object placements. The light data will give us the definition ID and thus the correct definition index to assign
    
    def build_tag(self, lights, scale=1):
        self.scale = scale
        if self.corinth:
            pass
        else:
            self._write_reach_light_definitions(lights)
            self._write_reach_light_instances(lights)
            
        self.tag_has_changes = True
        
    def _index_from_id(self, id):
        for element in self.block_generic_light_definitions.Elements:
            if element.SelectField("clipping planes x pos").GetStringData() == id:
                return element.ElementIndex
            
        return -1
        
    def _write_reach_light_instances(self, lights):
        self.block_generic_light_instances.RemoveAllElements()
        for light in lights:
            nwo = light.data.nwo
            element = self.block_generic_light_instances.AddElement()
            element.SelectField("definition index").SetStringData(str(self._index_from_id(get_light_id_from_data(light.data))))
            element.SelectField("shader reference index").SetStringData("-1")
            element.SelectField("origin").SetStringData([str(light.origin[0]),str(light.origin[1]),str(light.origin[2])])
            element.SelectField("forward").SetStringData([str(light.forward[0]),str(light.forward[1]),str(light.forward[2])])
            element.SelectField("up").SetStringData([str(light.up[0]),str(light.up[1]),str(light.up[2])])
            light_type = element.SelectField("bungie light type")
            match nwo.light_game_type:
                case "_connected_geometry_bungie_light_type_default":
                    light_type.Value = 0
                case "_connected_geometry_bungie_light_type_uber":
                    light_type.Value = 1
                case "_connected_geometry_bungie_light_type_inlined":
                    light_type.Value = 2
                case "_connected_geometry_bungie_light_type_screen_space":
                    light_type.Value = 3
                case "_connected_geometry_bungie_light_type_rerender":
                    light_type.Value = 4
                    
            flags = element.SelectField("screen space specular")
            flags.SetBit("screen space light has specular", nwo.light_game_type == '_connected_geometry_bungie_light_type_screen_space' and nwo.light_screenspace_has_specular)
            flags.SetBit("version 1 instances", True)
            element.SelectField("bounce light control").SetStringData(nwo_utils.jstr(nwo.light_bounce_ratio))
            element.SelectField("light volume distance").SetStringData(nwo_utils.jstr(nwo.light_volume_distance))
            element.SelectField("light volume intensity scalar").SetStringData(nwo_utils.jstr(nwo.light_volume_intensity))
            element.SelectField("fade start distance").SetStringData("100")
            element.SelectField("fade out distance").SetStringData("150")
            if nwo.light_tag_override:
                element.SelectField("user control").Path = self._TagPath_from_string(nwo.light_tag_override)
            if nwo.light_shader_reference:
                element.SelectField("shader reference").Path = self._TagPath_from_string(nwo.light_shader_reference)
            if nwo.light_gel_reference:
                element.SelectField("gel reference").Path = self._TagPath_from_string(nwo.light_gel_reference)
            if nwo.light_lens_flare_reference:
                element.SelectField("lens flare reference").Path = self._TagPath_from_string(nwo.light_lens_flare_reference)
        
    def _write_reach_light_definitions(self, lights):
        update_lights = set()
        to_remove_element_indexes = []
        light_ids = {get_light_id_from_data(light.data): light for light in lights}
        for element in self.block_generic_light_definitions.Elements:
            definition_id = element.SelectField("clipping planes x pos").GetStringData()
            found_light = light_ids.get(definition_id, None)
            if found_light is None:
                to_remove_element_indexes.append(element.ElementIndex)
            else:
                update_lights.add(found_light)
                
        for idx in reversed(to_remove_element_indexes):
            self.block_generic_light_definitions.RemoveElement(idx)
                
        new_lights = [light for light in lights if light not in update_lights]
            
        update_lights_data = {light.data for light in update_lights}
        new_lights_data = {light.data for light in new_lights}
        
        for data in update_lights_data:
            element_index = self._index_from_id(get_light_id_from_data(data))
            element = self.block_generic_light_definitions.Elements[element_index]
            self._update_reach_light_definition(element, data)
        
        for data in new_lights_data:
            element = self.block_generic_light_definitions.AddElement()
            # store id in clipping plane x pos
            element.SelectField("clipping planes x pos").SetStringData(get_light_id_from_data(data))
            self._update_reach_light_definition(element, data)
        
            
            
    def _update_reach_light_definition(self, element, data):
        nwo = data.nwo
        inverse_square = False
        type_field = element.SelectField("type")
        flags = element.SelectField("flags")
        flags.SetBit("use far attenuation", True)
        flags.SetBit("light version 1", True)
        if not nwo.light_far_attenuation_end:
            inverse_square = True
            flags.SetBit("invere squared falloff", True)
        if data.type == 'SUN':
            type_field.SetValue("directional")
        elif data.type == 'SPOT':
            type_field.SetValue("spot")
            hotspot_cutoff = min(degrees(data.spot_size), 160)
            hotspot_size = hotspot_cutoff * abs(1 - data.spot_blend)
            element.SelectField("hotspot cutoff size").SetStringData(nwo_utils.jstr(hotspot_cutoff))
            element.SelectField("hotspot size").SetStringData(nwo_utils.jstr(hotspot_size))
            element.SelectField("hotspot falloff speed").SetStringData(nwo_utils.jstr(nwo.light_falloff_shape))
        else:
            type_field.SetValue("omni")
            
        shape_field = element.SelectField("shape")
        if nwo.light_shape == '_connected_geometry_light_shape_circle':
            shape_field.SetValue("circle")
        else:
            shape_field.SetValue("rectangle")
        
        rgb_color = [str(nwo_utils.linear_to_srgb(data.color[0])), str(nwo_utils.linear_to_srgb(data.color[1])), str(nwo_utils.linear_to_srgb(data.color[2]))]
        element.SelectField('color').SetStringData(rgb_color)
        
        element.SelectField("intensity").SetStringData(nwo_utils.jstr(max(nwo_utils.calc_light_intensity(data), 0.0001)))
        element.SelectField("aspect").SetStringData(nwo_utils.jstr(nwo.light_aspect))
        near_attenuation = element.SelectField("near attenuation bounds")
        near_attenuation.SetStringData([nwo_utils.jstr(data.nwo.light_near_attenuation_start * 100 * self.scale * WU_SCALAR), nwo_utils.jstr(data.nwo.light_near_attenuation_end * 100  * self.scale * WU_SCALAR)])
        far_attenuation = element.SelectField("far attenuation bounds")
        if inverse_square:
            far_attenuation.SetStringData(["900", "4000"])
        else:
            far_attenuation.SetStringData([nwo_utils.jstr(data.nwo.light_far_attenuation_start * 100 * self.scale * WU_SCALAR), nwo_utils.jstr(data.nwo.light_far_attenuation_end * 100  * self.scale * WU_SCALAR)])
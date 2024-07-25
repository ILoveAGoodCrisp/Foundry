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

from io_scene_foundry.utils.nwo_utils import jstr
from io_scene_foundry.managed_blam import Tag

class ScenarioStructureBspTag(Tag):
    tag_ext = 'scenario_structure_bsp'
    
    def _read_fields(self):
        if self.corinth:
            self.block_prefabs = self.tag.SelectField("Block:external references")
    
    def write_prefabs(self, prefabs):
        if not self.corinth or (not prefabs and self.block_prefabs.Elements.Count == 0): return
        self.block_prefabs.RemoveAllElements()
        for prefab in prefabs:
            element = self.block_prefabs.AddElement()
            element.SelectField("prefab reference").Path = self._TagPath_from_string(prefab.reference)
            element.SelectField("name").SetStringData(prefab.name)
            element.SelectField("scale").SetStringData(prefab.scale)
            element.SelectField("forward").SetStringData(prefab.forward)
            element.SelectField("left").SetStringData(prefab.left)
            element.SelectField("up").SetStringData(prefab.up)
            element.SelectField("position").SetStringData(prefab.position)
            
            override_flags = element.SelectField("override flags")
            flags_mask = element.SelectField("instance flags Mask")
            policy_mask = element.SelectField("instance policy mask")
            
            nwo = prefab.props
            
            if nwo.prefab_lighting != "no_override":
                policy_mask.SetBit("override lightmapping policy", True)
                lighting = element.SelectField("override lightmapping policy")
                match nwo.prefab_lighting:
                    case "_connected_geometry_poop_lighting_per_pixel":
                        lighting.Value = 0
                    case "_connected_geometry_poop_lighting_per_vertex":
                        lighting.Value = 1
                    case "_connected_geometry_poop_lighting_single_probe":
                        lighting.Value = 2
                    case "_connected_geometry_poop_lighting_per_vertex_ao":
                        lighting.Value = 5
                    
            if nwo.prefab_pathfinding != "no_override":
                policy_mask.SetBit("override pathfinding policy", True)
                pathfinding = element.SelectField("override pathfinding policy")
                match nwo.prefab_lighting:
                    case "_connected_poop_instance_pathfinding_policy_cutout":
                        pathfinding.Value = 0
                    case "_connected_poop_instance_pathfinding_policy_static":
                        pathfinding.Value = 1
                    case "_connected_poop_instance_pathfinding_policy_none":
                        pathfinding.Value = 2
                        
            if nwo.prefab_imposter_policy != "no_override":
                policy_mask.SetBit("override lmposter policy", True)
                imposter = element.SelectField("override imposter policy")
                match nwo.prefab_imposter_policy:
                    case "_connected_poop_instance_imposter_policy_polygon_default":
                        imposter.Value = 0
                    case "_connected_poop_instance_imposter_policy_polygon_high":
                        imposter.Value = 1
                    case "_connected_poop_instance_imposter_policy_card_default":
                        imposter.Value = 2
                    case "_connected_poop_instance_imposter_policy_card_high":
                        imposter.Value = 3
                    case "_connected_poop_instance_imposter_policy_never":
                        imposter.Value = 4
                if nwo.prefab_imposter_policy != "_connected_poop_instance_imposter_policy_never":
                    if nwo.prefab_imposter_brightness > 0:
                        policy_mask.SetBit("override imposter brightness", True)
                        element.SelectField("override imposter brightness").SetStringData(jstr(nwo.prefab_imposter_brightness))
                        
                    if not nwo.prefab_imposter_transition_distance_auto:
                        policy_mask.SetBit("override imposter transition distance policy", True)
                        element.SelectField("override imposter transition distance").SetStringData(jstr(nwo.prefab_imposter_transition_distance))
                        
            if nwo.prefab_streaming_priority != "no_override":
                streaming = element.SelectField("override streaming priority")
                match nwo.prefab_streaming_priority:
                    case "_connected_geometry_poop_streamingpriority_default":
                        streaming.Value = 0
                    case "_connected_geometry_poop_streamingpriority_higher":
                        streaming.Value = 1
                    case "_connected_geometry_poop_streamingpriority_highest":
                        streaming.Value = 2
            
            if nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_only':
                override_flags.SetBit("cinema only", True)
                flags_mask.SetBit("cinema only", True)
            elif nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_exclude':
                override_flags.SetBit("exclude from cinema", True)
                flags_mask.SetBit("exclude from cinema", True)
                
            if nwo.prefab_render_only:
                override_flags.SetBit("render only", True)
                flags_mask.SetBit("render only", True)
            if nwo.prefab_does_not_block_aoe:
                override_flags.SetBit("does not block aoe damage", True)
                flags_mask.SetBit("does not block aoe damage", True)
            if nwo.prefab_excluded_from_lightprobe:
                override_flags.SetBit("not in lightprobes", True)
                flags_mask.SetBit("not in lightprobes", True)
            if nwo.prefab_decal_spacing:
                override_flags.SetBit("decal spacing", True)
                flags_mask.SetBit("decal spacing", True)
            if nwo.prefab_remove_from_shadow_geometry:
                override_flags.SetBit("remove from shadow geometry", True)
                flags_mask.SetBit("remove from shadow geometry", True)
            if nwo.prefab_disallow_lighting_samples:
                override_flags.SetBit("disallow object lighting samples", True)
                flags_mask.SetBit("disallow object lighting samples", True)
            
        self.tag_has_changes = True
            
        
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

from io_scene_foundry import icons
from io_scene_foundry.utils import nwo_utils

class NWOAsset:
    def __init__(self, internal_name: str, display_name: str, icon: str, corinth_only: bool, description="") -> None:
        self.internal_name = internal_name
        self.display_name = display_name
        self.icon_name = icon
        self.corinth_only = corinth_only
        self.description = description
        
    @property
    def icon(self):
        if self.icon_name.upper() == self.icon_name:
            return self.icon_name
        return icons.get_icon_id(self.icon_name)
    
model_description = "Models are objects that can be placed down in scenarios.\n\nThey must always have a render model, but can optionally have collision and physics models, as well as animation graphs.\n\nModels may be generated as a variety of high level tags, such as scenery, vehicles, weapons etc"
scenario_description = "Scenarios are playable levels. They are made up of BSPs which make up the level geometry for the scenario"
sky_description = "Skies are used for scenarios as a skybox.\n\nThey may contain lights which can be used when lightmapping a scenario. Skies contain only render geometry"
decorator_set_description = "Decorator sets are used as paint brushes in scenarios.\n\nThey are made up of a set of render geometry that can then be painted onto scenario geometry"
particle_model_description = "Particle models are used for particle emitters in effect tags"
animation_description = "Animation graphs enable animations to play on objects.\n\nUnlike the model asset type, this type only generates an animation graph.\n\nUse this if you are creating first person animations or standalone/cinematic animations"
camera_track_set_description = "Camera tracks represent the position of a third person camera on a unit (such as a vehicle) at different look angles"
resource_description = "Resource assets cannot be exported but offer access to all object/mesh/marker types and tools.\n\nThey are designed to contain data (such as materials of meshes) that can then be referenced in other scenes"
prefab_description = "Prefabs act like standalone bits of instanced geometry that can be referenced in BSPs.\n\nTo reference a prefab in a Scenario asset, add a Game Object Marker and add the relative tag path to your the tag path field"
  
model = NWOAsset("model", "Model", "model", False, model_description)
scenario = NWOAsset("scenario", "Scenario", "scenario", False, scenario_description)
sky = NWOAsset("sky", "Sky", "sky", False, sky_description)
decorator_set = NWOAsset("decorator_set", "Decorator Set", "decorator", False, decorator_set_description)
particle_model = NWOAsset("particle_model", "Particle Model", "particle_model", False, particle_model_description)
animation = NWOAsset("animation", "Animation Graph", "animation", False, animation_description)
camera_track_set = NWOAsset("camera_track_set", "Camera Track Set", 'CON_CAMERASOLVER', False, camera_track_set_description)
resource = NWOAsset("resource", "Resource", "LINKED", False, resource_description)
prefab = NWOAsset("prefab", "Prefab", "prefab", True, prefab_description)

asset_types = [model, scenario, sky, decorator_set, particle_model, animation, camera_track_set, resource, prefab]

def asset_type_items(self, context):
    items = []
    corinth = nwo_utils.is_corinth(context)
    for i, a in enumerate([a for a in asset_types if corinth or not a.corinth_only]):
        items.append((a.internal_name, a.display_name, a.description, a.icon, i))
    
    return items
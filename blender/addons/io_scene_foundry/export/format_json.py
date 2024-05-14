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

import bpy
from ..utils.nwo_utils import is_corinth

class NWOJSON(dict):
    def __init__(
        self,
        objects,
        sidecar_type,
        model_armature,
        world_frame,
        asset_name,
        bone_list,
        validated_regions,
        validated_permutations,
        global_materials_dict,
        skylights,
    ):
        self.objects = objects
        self.sidecar_type = sidecar_type
        self.model_armature = model_armature
        self.corinth = is_corinth()
        self.world_frame = world_frame
        self.asset_name = asset_name
        self.bone_list = bone_list
        self.validated_regions = validated_regions
        self.validated_permutations = validated_permutations
        self.global_materials_dict = global_materials_dict
        self.skylights = skylights
        self.string_table = self.build_string_table()
        self.nodes_properties, self.meshes_properties = self.build_nodes_meshes_properties()
        if self.skylights and self.meshes_properties:
            holder_of_light = self.meshes_properties[list(self.meshes_properties.keys())[0]]
            holder_of_light.update(self.skylights)
            
        # self.material_properties = self.build_material_properties()

        self.json_dict = {}
        self.json_dict.update({"string_table": self.string_table})
        self.json_dict.update({"nodes_properties": self.nodes_properties})
        self.json_dict.update({"meshes_properties": self.meshes_properties})
        # self.json_dict.update({"material_properties": self.material_properties})

    # STRING TABLE
    def build_string_table(self):
        global_materials = self.get_global_materials()
        regions = self.get_regions()
        table = {}
        if self.sidecar_type in ("model", "scenario", "prefab", "sky"):
            table.update({"global_materials_names": list(global_materials.keys())})
            table.update({"global_materials_values": list(global_materials.values())})
        if self.sidecar_type in ("model", "sky"):
            table.update({"regions_names": regions})
            table.update({"regions_values": [str(regions.index(region)) for region in regions]})

        return table

    def get_global_materials(self):
        keep_list = ["default"]
        for global_material in self.global_materials_dict.keys():
            for ob in self.objects:
                if (
                    global_material not in keep_list
                    and ob.nwo.face_global_material == global_material
                ):
                    keep_list.append(global_material)

        global_materials_list = {}
        global_materials_list.update(self.global_materials_dict)
        for key in self.global_materials_dict.keys():
            if key not in keep_list:
                global_materials_list.pop(key)

        return global_materials_list

    def get_regions(self):
        keep_regions = []
        for name in self.validated_regions:
            for ob in self.objects:
                if name not in keep_regions and ob.nwo.region_name == name:
                    keep_regions.append(name)

        return keep_regions

    def build_nodes_meshes_properties(self):
        node_properties = {}
        mesh_properties = {}
        node_properties.update(self.bone_list)
        # build frame props
        for ob in self.objects:
            if ob.type == "MESH":
                mesh_properties[ob.name] = self.get_halo_props(ob)
            else:
                node_properties[ob.name] = self.get_halo_props(ob)

        return node_properties, mesh_properties
    
    def get_halo_props(self, id) -> dict:
        halo_props = {k: v for k, v in id.items() if type(k) == str and k.startswith('bungie_')}
        if isinstance(id, bpy.types.Object):
            halo_props["bungie_object_ID"] = id.nwo.ObjectID
            
        return halo_props
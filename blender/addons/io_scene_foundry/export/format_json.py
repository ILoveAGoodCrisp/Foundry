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

from ..utils.nwo_utils import is_corinth
from .nwo_format import (
    NWOFrame,
    NWOLight,
    NWOMarker,
    NWOMesh,
    NWOAnimationEvent,
    NWOAnimationControl,
    NWOAnimationCamera,
    NWOFramePCA,
    NWOMaterial,
)


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
            
        self.material_properties = self.build_material_properties()

        self.json_dict = {}
        self.json_dict.update({"string_table": self.string_table})
        self.json_dict.update({"nodes_properties": self.nodes_properties})
        self.json_dict.update({"meshes_properties": self.meshes_properties})
        self.json_dict.update({"material_properties": self.material_properties})

    # STRING TABLE
    def build_string_table(self):
        global_materials = self.get_global_materials()
        regions = self.get_regions()
        table = {}
        if self.sidecar_type in ("MODEL", "SCENARIO", "PREFAB", "SKY"):
            table.update({"global_materials_names": list(global_materials.keys())})
            table.update({"global_materials_values": list(global_materials.values())})
        if self.sidecar_type in ("MODEL", "SKY"):
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
            nwo = ob.nwo
            match nwo.object_type:
                case "_connected_geometry_object_type_animation_event":
                    props = NWOAnimationEvent(
                        ob,
                        self.sidecar_type,
                        self.model_armature,
                        self.world_frame,
                        self.asset_name,
                        self.validated_permutations,
                    )
                    node_properties.update({ob.name: props.__dict__})
                case "_connected_geometry_object_type_animation_control":
                    props = NWOAnimationControl(
                        ob,
                        self.sidecar_type,
                        self.model_armature,
                        self.world_frame,
                        self.asset_name,
                        self.validated_permutations,
                    )
                    node_properties.update({ob.name: props.__dict__})
                case "_connected_geometry_object_type_animation_camera":
                    props = NWOAnimationCamera(
                        ob,
                        self.sidecar_type,
                        self.model_armature,
                        self.world_frame,
                        self.asset_name,
                        self.validated_permutations,
                    )
                    node_properties.update({ob.name: props.__dict__})
                case "_connected_geometry_object_type_light":
                    props = NWOLight(
                        ob,
                        self.sidecar_type,
                        self.model_armature,
                        self.world_frame,
                        self.asset_name,
                        self.validated_permutations,
                    )
                    node_properties.update({ob.name: props.__dict__})
                case "_connected_geometry_object_type_marker":
                    props = NWOMarker(
                        ob,
                        self.sidecar_type,
                        self.model_armature,
                        self.world_frame,
                        self.asset_name,
                        self.validated_permutations,
                    )
                    node_properties.update({ob.name: props.__dict__})
                case "_connected_geometry_object_type_frame_pca":
                    props = NWOFramePCA(
                        ob,
                        self.sidecar_type,
                        self.model_armature,
                        self.world_frame,
                        self.asset_name,
                        self.validated_permutations,
                    )
                    node_properties.update({ob.name: props.__dict__})
                case "_connected_geometry_object_type_frame":
                    props = NWOFrame(
                        ob,
                        self.sidecar_type,
                        self.model_armature,
                        self.world_frame,
                        self.asset_name,
                        self.validated_permutations,
                    )
                    node_properties.update({ob.name: props.__dict__})
                case "_connected_geometry_object_type_mesh":
                    props = NWOMesh(
                        ob,
                        self.sidecar_type,
                        self.model_armature,
                        self.world_frame,
                        self.asset_name,
                        self.validated_permutations,
                    )
                    mesh_properties.update({ob.name: props.__dict__})

        return node_properties, mesh_properties

    def build_material_properties(self):
        # first, get all materials for the selected objects
        materials = []
        for ob in self.objects:
            for slot in ob.material_slots:
                if slot.material is not None and slot.material not in materials:
                    materials.append(slot.material)

        material_properties = {}
        # build material props
        for mat in materials:
            props = NWOMaterial(mat)
            material_properties.update({mat.name: props.__dict__})

        return material_properties

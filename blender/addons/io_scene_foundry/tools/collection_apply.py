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

from io_scene_foundry.utils.nwo_utils import any_partition

class NWO_ApplyCollectionMenu(bpy.types.Menu):
    bl_label = "Halo Collection Menu"
    bl_idname = "NWO_MT_ApplyCollectionMenu"

    def draw(self, context):
        layout = self.layout
        is_scenario = context.scene.nwo.asset_type in ('SCENARIO', 'PREFAB')
        r_name = "Region"
        p_name = "Permutation"
        if is_scenario:
            r_name = "BSP"
            p_name = "Layer"
        
        layout.operator('nwo.apply_type_collection', text="None").c_type = "none"
        layout.operator_menu_enum('nwo.region_collection_list', property='name', text=r_name).c_type = 'region'
        layout.operator_menu_enum('nwo.permutation_collection_list', property='name', text=p_name).c_type = 'permutation'
        layout.operator('nwo.apply_type_collection', text="Exclude").c_type = "exclude"

class NWO_ApplyCollectionType(bpy.types.Operator):
    bl_idname = "nwo.apply_type_collection"
    bl_label = "Apply Collection Type"
    bl_description = "Sets the Halo Collection Type of the the selected collection"

    collection : bpy.props.StringProperty()

    name : bpy.props.StringProperty()

    def type_items(self, context):
        items = []
        r_name = "Region"
        p_name = "Permutation"
        if context.scene.nwo.asset_type == "SCENARIO":
            r_name = "BSP"
            p_name = "Layer"

        items.append(("none", "None", ""))
        items.append(("region", r_name, ""))
        items.append(("permutation", p_name, ""))
        items.append(("exclude", "Exclude", ""))

        return items

    c_type: bpy.props.EnumProperty(
        name="Collection Type",
        items=type_items,
        )

    def execute(self, context):
        if self.c_type == 'exclude':
            self.name = any_partition(context.collection.name, '::', True)
        if self.collection:
            coll = bpy.data.collections[self.collection]
        else:
            if not context.collection:
                return {'CANCELLED'}
            coll = context.collection
        # Setting the nwo collection type
        coll.nwo.type = self.c_type
        coll_name = self.name.lower()[:128]
        if self.c_type == 'none':
            coll.name = any_partition(coll.name, '::', True)
            return {'FINISHED'}

        display_name = self.c_type
        is_scenario = context.scene.nwo.asset_type in ('SCENARIO', 'PREFAB')
        if self.c_type == 'region':
            if is_scenario:
                display_name = 'bsp'

            regions = context.scene.nwo.regions_table
            coll.nwo.region = coll_name
            if coll_name not in [r.name for r in regions]:
                new_region = regions.add()
                new_region.name = coll_name

        elif self.c_type == 'permutation':
            if is_scenario:
                display_name = 'layer'
            permutations = context.scene.nwo.permutations_table
            coll.nwo.permutation = coll_name
            if coll_name not in [p.name for p in permutations]:
                new_permutation = permutations.add()
                new_permutation.name = coll_name

        coll.name = display_name + '::' + coll_name

        return {'FINISHED'}
    
class NWO_PermutationListCollection(NWO_ApplyCollectionType):
    bl_idname = "nwo.permutation_collection_list"
    bl_label = "Permutation List"
    bl_description = "Applies a permutation to the selected collection"

    def permutation_items(self, context):
        items = []

        perms = context.scene.nwo.permutations_table
        for p in perms:
            items.append((p.name, p.name, ''))

        return items

    name: bpy.props.EnumProperty(
        items=permutation_items,
    )
    
class NWO_RegionListCollection(NWO_ApplyCollectionType):
    bl_idname = "nwo.region_collection_list"
    bl_label = "Region List"
    bl_description = "Applies a region to the selected collection"

    def region_items(self, context):
        items = []

        regions = context.scene.nwo.regions_table
        for r in regions:
            items.append((r.name, r.name, ''))

        return items

    name: bpy.props.EnumProperty(
        items=region_items,
    )
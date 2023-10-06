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

import bpy

class NWO_CollectionPropertiesGroup(bpy.types.PropertyGroup):

    def type_items(self, context):
        items = []
        r_name = "Region"
        p_name = "Permutation"
        if context.scene.nwo.asset_type == "SCENARIO":
            r_name = "BSP"
            p_name = "BSP Category"

        items.append(("none", "None", ""))
        items.append(("region", r_name, ""))
        items.append(("permutation", p_name, ""))
        items.append(("exclude", "Exclude", ""))

        return items

    type: bpy.props.EnumProperty(
        name="Collection Type",
        items=type_items,
        )
    
    def get_region(self):
        scene_nwo = bpy.context.scene.nwo
        regions = scene_nwo.regions_table
        name = self.get("region", "")
        if not regions:
            return "default"
        region_names = [r.name for r in regions]
        if name not in region_names:
            name = scene_nwo.regions_table[0].name
        self['region'] = name
        return name

    def set_region(self, value):
        self['region'] = value

    region: bpy.props.StringProperty(
        name="Region",
        set=set_region,
        get=get_region,
    )

    def get_permutation(self):
        scene_nwo = bpy.context.scene.nwo
        permutations = scene_nwo.permutations_table
        name = self.get("permutation", "")
        if not permutations:
            return "default"
        permutation_names = [p.name for p in permutations]
        if name not in permutation_names:
            name = scene_nwo.permutations_table[0].name
        self['permutation'] = name
        return name

    def set_permutation(self, value):
        self['permutation'] = value

    permutation: bpy.props.StringProperty(
        name="Permutation",
        set=set_permutation,
        get=get_permutation,
    )
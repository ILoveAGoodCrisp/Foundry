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

from io_scene_foundry.utils import nwo_utils

class SpecialMaterial:
    def __init__(self, name: str, games: list, asset_types: list, color: list[float]):
        self.name = name
        self.games = games
        self.asset_types = asset_types
        self.color = color
    
invisible = SpecialMaterial('+invisible', ['reach', 'h4'], ['MODEL', 'SKY', 'SCENARIO', 'PREFAB'], [1, 1, 1, 0])
seamsealer = SpecialMaterial('+seamsealer', ['reach',], ['SCENARIO',], [1, 1, 1, 0.05])
sky = SpecialMaterial('+sky', ['reach',], ['SCENARIO',], [0.5, 0.7, 1, 0.05])

special_materials = invisible, seamsealer, sky

class NWO_AppendFoundryMaterials(bpy.types.Operator):
    bl_idname = "nwo.append_foundry_materials"
    bl_label = "Append Special Materials"
    bl_description = "Appends special materials relevant to the current project and asset type to the blend file. Special materials are noted by their '+' prefix"
    bl_options = {"UNDO"}

    def execute(self, context):
        game = 'h4' if nwo_utils.is_corinth(context) else 'reach'
        asset_type = context.scene.nwo.asset_type
        blender_materials = bpy.data.materials
        count = 0
        for m in special_materials:
            if game in m.games and asset_type in m.asset_types and not blender_materials.get(m.name):
                mat = blender_materials.new(m.name)
                mat.use_fake_user = True
                mat.use_nodes = False
                mat.diffuse_color = m.color
                count += 1
        
        if count == 0:
            self.report({'INFO'}, 'All relevant special materials already added to blend file')
        else:
            self.report({'INFO'}, f'Added {count} material{"s" if count > 1 else ""} to blend file')
        return {"FINISHED"}

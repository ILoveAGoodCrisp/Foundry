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

from io_scene_foundry.utils import nwo_utils
from io_scene_foundry.utils.nwo_materials import special_materials

class NWO_AppendFoundryMaterials(bpy.types.Operator):
    bl_idname = "nwo.append_foundry_materials"
    bl_label = "Append Special Materials"
    bl_description = "Appends special materials relevant to the current project and asset type to the blend file. Special materials are denoted by their '+' prefix"
    bl_options = {"UNDO"}

    def execute(self, context):
        game = 'h4' if nwo_utils.is_corinth(context) else 'reach'
        asset_type = context.scene.nwo.asset_type
        count = add_special_materials(game, asset_type)
        
        if count == 0:
            self.report({'INFO'}, 'All relevant special materials already added to blend file')
        else:
            self.report({'INFO'}, f'Added {count} material{"s" if count > 1 else ""} to blend file')
        return {"FINISHED"}
    
def add_special_materials(game, asset_type):
    blender_materials = bpy.data.materials
    count = 0
    for m in special_materials:
        if game in m.games and asset_type in m.asset_types and not blender_materials.get(m.name):
            mat = blender_materials.new(m.name)
            mat.use_fake_user = True
            mat.diffuse_color = m.color
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes[0]
            bsdf.inputs[0].default_value = m.color
            bsdf.inputs[4].default_value = m.color[3]
            mat.blend_method = 'BLEND'
            mat.shadow_method = 'NONE'
            count += 1
            
    return count
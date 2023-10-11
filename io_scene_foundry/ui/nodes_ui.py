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
import os
from io_scene_foundry.utils.nwo_utils import is_corinth

MATERIAL_RESOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'resources', 'materials')

def node_context_menu(self, context):
    entry_name = 'Halo Shaders'
    if is_corinth(context):
        entry_name = 'Halo Material Shaders'
    else:
        return # temp as Reach custom shaders not implemented
    layout = self.layout
    layout.separator()
    layout.operator_menu_enum('nwo.halo_material_nodes', 'node', text=entry_name)
    layout.operator('nwo.halo_material_tile_node', text='Halo Texture Tiling Node')

class NWO_HaloMaterialTilingNode(bpy.types.Operator):
    bl_idname = 'nwo.halo_material_tile_node'
    bl_label = ''
    bl_description = 'Adds a Halo texture tiling node. This node should plug into the vector input of an image texture node'

    def execute(self, context):
        tiling_node = 'Texture Tiling'
        lib_blend = os.path.join(MATERIAL_RESOURCES, 'shared_nodes.blend')
        with bpy.data.libraries.load(lib_blend, link=True) as (_, data_to):
            if not bpy.data.node_groups.get(tiling_node, 0):
                data_to.node_groups = [tiling_node]

        if bpy.data.node_groups.get(tiling_node, 0):
            bpy.ops.node.add_node('INVOKE_DEFAULT', use_transform=True, settings=[{"name":"node_tree", "value":f"bpy.data.node_groups['{tiling_node}']"}], type="ShaderNodeGroup")
        else:
            self.report({'ERROR', 'Failed to add node'})
            return {'CANCELLED'}

        return {'FINISHED'}

class NWO_HaloMaterialNodes(bpy.types.Operator):
    bl_idname = 'nwo.halo_material_nodes'
    bl_label = ''
    bl_description = 'Adds a Halo Material Node. This should plug into the Surface input of the Material Output node'

    def nodes_items(self, context):
        items = []
        if is_corinth(context):
            lib_blend = os.path.join(MATERIAL_RESOURCES, 'h4_nodes.blend')
        else:
            lib_blend = os.path.join(MATERIAL_RESOURCES, 'hr_nodes.blend')
        
        with bpy.data.libraries.load(lib_blend, link=True) as (data_from, _):
            for n_group in data_from.node_groups:
                items.append((n_group, n_group, 'Texture Tiling'))


        return items    

    node: bpy.props.EnumProperty(
        name='Node',
        items=nodes_items,
    )
    
    def execute(self, context):
        if not self.node:
            return {'CANCELLED'}
        
        if is_corinth(context):
            lib_blend = os.path.join(MATERIAL_RESOURCES, 'h4_nodes.blend')
        else:
            lib_blend = os.path.join(MATERIAL_RESOURCES, 'hr_nodes.blend')

        # This bit links the selected node to the current blend
        with bpy.data.libraries.load(lib_blend, link=True) as (_, data_to):
            if not bpy.data.node_groups.get(self.node, 0):
                data_to.node_groups = [self.node]

        # This bit adds the node itself
        if bpy.data.node_groups.get(self.node, 0):
            bpy.ops.node.add_node('INVOKE_DEFAULT', use_transform=True, settings=[{"name":"node_tree", "value":f"bpy.data.node_groups['{self.node}']"}], type="ShaderNodeGroup")
        else:
            self.report({'ERROR', 'Failed to add node'})
            return {'CANCELLED'}
        return {'FINISHED'}
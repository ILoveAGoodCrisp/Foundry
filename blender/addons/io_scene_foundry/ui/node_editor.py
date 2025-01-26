"""UI that sits in the Blender node editor"""

import os
from pathlib import Path
import bpy
from .. import utils

all_material_shaders = []

def node_context_menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator('nwo.halo_material_tile_node', text='Halo Texture Tiling Node')
    if utils.is_corinth(context):
        entry_name = 'Halo Material Shaders'
    else:
        entry_name = 'Halo Shaders'
        return # temp as Reach custom shaders not implemented
    layout.operator_menu_enum('nwo.halo_material_nodes', 'node', text=entry_name)

class NWO_OT_HaloMaterialTilingNode(bpy.types.Operator):
    bl_idname = 'nwo.halo_material_tile_node'
    bl_label = ''
    bl_description = 'Adds a Halo texture tiling node. This node should plug into the vector input of an image texture node'
    
    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'NODE_EDITOR' and context.material and context.material.use_nodes

    def execute(self, context):
        tiling_node = 'Texture Tiling'
        utils.add_node_from_resources("shared_nodes", tiling_node)

        if bpy.data.node_groups.get(tiling_node, 0):
            bpy.ops.node.add_node('INVOKE_DEFAULT', use_transform=True, settings=[{"name":"node_tree", "value":f"bpy.data.node_groups['{tiling_node}']"}], type="ShaderNodeGroup")
        else:
            self.report({'ERROR', 'Failed to add node'})
            return {'CANCELLED'}
        return {'FINISHED'}

class NWO_OT_HaloMaterialNodes(bpy.types.Operator):
    bl_idname = 'nwo.halo_material_nodes'
    bl_label = ''
    bl_description = 'Adds a Halo Material Node. This should plug into the Surface input of the Material Output node'

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'NODE_EDITOR' and context.material and context.material.use_nodes

    def nodes_items(self, context):
        items = []
        h4 = utils.is_corinth(context)
        if h4:
            lib_blend = Path(utils.MATERIAL_RESOURCES, 'h4_nodes.blend')
        else:
            lib_blend = Path(utils.MATERIAL_RESOURCES, 'hr_nodes.blend')
        
        with bpy.data.libraries.load(lib_blend, link=True) as (data_from, _):
            for n_group in data_from.node_groups:
                if not h4:
                    items.append((n_group, n_group, ''))
                else:
                    global all_material_shaders
                    if not all_material_shaders:
                        tags_dir = utils.get_tags_path()
                        material_shaders_dir = Path(tags_dir, 'shaders')
                        for root, _, files in os.walk(material_shaders_dir):
                            for file in files:
                                if file.endswith(".material_shader"):
                                    all_material_shaders.append(utils.dot_partition(file))
                    if n_group in all_material_shaders:
                        items.append((n_group, n_group, ''))
        return items    

    node: bpy.props.EnumProperty(
        name='Node',
        items=nodes_items,
    )
    
    def execute(self, context):
        if not self.node:
            return {'CANCELLED'}
        
        if utils.is_corinth(context):
            lib_blend = os.path.join(utils.MATERIAL_RESOURCES, 'h4_nodes.blend')
        else:
            lib_blend = os.path.join(utils.MATERIAL_RESOURCES, 'hr_nodes.blend')

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
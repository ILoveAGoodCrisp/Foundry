"""UI that sits in the Blender node editor"""

import os
from pathlib import Path
import bpy
from .. import utils

SHADER_LIBRARIES = {
    'halo1': ('h1_nodes.blend', 'foundry_h1.'),
    'halo2': ('h2_nodes.blend', None),
    'halo3': ('h3_nodes.blend', 'foundry_h3.'),
    'halo3odst': ('h3_nodes.blend', 'foundry_h3odst.'),
    'reach': ('reach_nodes.blend', 'foundry_reach.'),
    'halo4': ('h4_nodes.blend', None),
    'halo2a': ('h4_nodes.blend', None),
}
SEARCHABLE_SHADER_GAMES = {'halo2', 'halo4', 'halo2a'}
# Keep dynamic enum strings alive, and scope catalogs to their game and project.
_node_items = {}


def shader_node_items(context, *, refresh=False):
    if context is None:
        return []
    game = utils.get_game(context.scene.nwo.scene_project)
    library_name, prefix = SHADER_LIBRARIES[game]
    library = Path(utils.MATERIAL_RESOURCES, library_name)
    project = utils.get_project(context.scene.nwo.scene_project)
    tags_dir = project.tags_directory if project and game in {'halo4', 'halo2a'} else ''
    if not library.is_file():
        return []
    key = (game, str(library), library.stat().st_mtime_ns, tags_dir)
    if key in _node_items and not refresh:
        return _node_items[key]

    material_shaders = set()
    if tags_dir:
        for _, _, files in os.walk(Path(tags_dir, 'shaders')):
            material_shaders.update(Path(file).stem for file in files
                                    if file.endswith('.material_shader'))

    items = []
    with bpy.data.libraries.load(str(library), link=True) as (data_from, _):
        for name in data_from.node_groups:
            if prefix:
                family = name.removeprefix(prefix)
                if not name.startswith(prefix) or f'.{family}' not in utils.shader_exts:
                    continue
                display_name = family.replace('_', ' ').title()
            elif game == 'halo2':
                if name.startswith('.') or name == 'Basic H2 environment_map reflector':
                    continue
                display_name = name.replace('_', ' ').title()
            else:
                if name not in material_shaders:
                    continue
                display_name = name.replace('_', ' ').title()
            items.append((name, display_name, name))
    _node_items[key] = sorted(items, key=lambda item: (item[1].casefold(), item[0]))
    return _node_items[key]

def node_context_menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator('nwo.halo_material_tile_node', text='Halo Texture Tiling Node')
    game = utils.get_game(context.scene.nwo.scene_project)
    if game in {'halo4', 'halo2a'}:
        entry_name = 'Halo Material Shaders'
    else:
        entry_name = 'Halo Shaders'
    if NWO_OT_HaloMaterialNodes.poll(context):
        shader_node_items(context, refresh=True)
    if game in SEARCHABLE_SHADER_GAMES:
        row = layout.row()
        row.operator_context = 'INVOKE_DEFAULT'
        row.operator('nwo.halo_material_nodes', text=entry_name + '...', icon='VIEWZOOM')
    else:
        layout.operator_menu_enum('nwo.halo_material_nodes', 'node', text=entry_name)

class NWO_OT_HaloMaterialTilingNode(bpy.types.Operator):
    bl_idname = 'nwo.halo_material_tile_node'
    bl_label = ''
    bl_description = 'Adds a Halo texture tiling node. This node should plug into the vector input of an image texture node'
    
    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'NODE_EDITOR' and context.material

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
    bl_label = 'Add Halo Shader'
    bl_description = 'Adds a Halo Material Node connected through the Foundry Node to the material output'
    bl_options = {'UNDO'}
    bl_property = 'node'

    @classmethod
    def poll(cls, context):
        return (context.space_data is not None and context.space_data.type == 'NODE_EDITOR'
                and context.space_data.tree_type == 'ShaderNodeTree'
                and context.material is not None and context.material.node_tree is not None)

    def nodes_items(self, context):
        return shader_node_items(context)

    node: bpy.props.EnumProperty(
        name='Node',
        items=nodes_items,
    )
    
    def execute(self, context):
        if not self.node:
            return {'CANCELLED'}
        if self.node not in {item[0] for item in shader_node_items(context)}:
            self.report({'ERROR'}, 'Shader template is not available for the current project')
            return {'CANCELLED'}
        game = utils.get_game(context.scene.nwo.scene_project)
        lib_blend = Path(utils.MATERIAL_RESOURCES, SHADER_LIBRARIES[game][0])
        # Use the linked datablock returned by this library, even when a local
        # group or a different library already contains the same name.
        node_group = bpy.data.node_groups.get((self.node, str(lib_blend)))
        if node_group is None:
            with bpy.data.libraries.load(str(lib_blend), link=True) as (_, data_to):
                data_to.node_groups = [self.node]
            node_group = data_to.node_groups[0]

        if node_group is not None:
            tree = context.material.node_tree
            shader = tree.nodes.new('ShaderNodeGroup')
            shader.node_tree = node_group
            if (shader.node_tree.get('h2_preview_transparent_placeholder') or
                    shader.node_tree.get('h2_surface_mode','opaque') != 'opaque' or shader.node_tree.get('h2_multichannel_revision')):
                context.material.surface_render_method = 'BLENDED'
            foundry = utils.update_foundry_material(context.material, arrange_nodes=False)
            surface = next((socket for socket in shader.outputs if socket.type == 'SHADER'), None)
            if surface is not None:
                tree.links.new(surface, foundry.inputs['Shader'])
            tree.nodes.active = shader
            utils.arrange(tree)
        else:
            self.report({'ERROR'}, 'Failed to add node')
            return {'CANCELLED'}
        return {'FINISHED'}

    def invoke(self, context, event):
        if self.properties.is_property_set('node'):
            return self.execute(context)
        if not shader_node_items(context, refresh=True):
            self.report({'WARNING'}, 'No shader templates are available for the current project')
            return {'CANCELLED'}
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

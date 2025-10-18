import os
from pathlib import Path
import bpy

from .node_tree_arrange import arrange
from ..managed_blam.shader_glass import ShaderGlassTag
from ..managed_blam.shader_custom import ShaderCustomTag
from ..managed_blam.shader_halogram import ShaderHalogramTag
from ..managed_blam.shader_foliage import ShaderFoliageTag
from ..managed_blam.shader_terrain import ShaderTerrainTag
from ..managed_blam.material import MaterialTag
from ..managed_blam.shader import ShaderTag
from ..managed_blam.shader_decal import ShaderDecalTag
from .. import utils

class NWO_OT_ShaderToNodesBulk(bpy.types.Operator):
    bl_idname = "nwo.shader_to_nodes_bulk"
    bl_label = "Convert all Shaders to Blender Material Nodes"
    bl_description = "Builds blender materials for all shaders"
    bl_options = {"UNDO"}
    
    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always extract bitmaps",
        description="By default existing tiff files will be used for shaders. Checking this option means the bitmaps will always be re-extracted regardless if they exist or not"
    )

    @classmethod
    def poll(cls, context):
        return not context.scene.nwo.export_in_progress
    
    def execute(self, context):
        corinth = utils.is_corinth(context)
        
        os.system("cls")
        if context.scene.nwo_export.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            print(f"Building Blender Materials\n")
        
        built_count = 0
        for mat in bpy.data.materials:
            if not mat.nwo.RenderMaterial:
                continue
            
            built_count += 1
            shader_path = utils.relative_path(mat.nwo.shader_path)
            full_path = Path(utils.get_tags_path(), shader_path)
            if not full_path.exists():
                continue
            
            tag_to_nodes(corinth, mat, shader_path)
            
        self.report({'INFO'}, f"Built {built_count} blender materials")
        return {"FINISHED"}
    
    def invoke(self, context: bpy.types.Context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "always_extract_bitmaps")

class NWO_ShaderToNodes(bpy.types.Operator):
    bl_idname = "nwo.shader_to_nodes"
    bl_label = "Convert Shader to Blender Material Nodes"
    bl_description = "Builds a new node tree for the active material based on the referenced shader/material tag. Will import required bitmaps"
    bl_options = {"UNDO"}
    
    mat_name: bpy.props.StringProperty()
    
    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always extract bitmaps",
        description="By default existing tiff files will be used for shaders. Checking this option means the bitmaps will always be re-extracted regardless if they exist or not"
    )

    @classmethod
    def poll(cls, context):
        return not context.scene.nwo.export_in_progress

    def execute(self, context):
        mat = bpy.data.materials.get(self.mat_name, 0)
        if not mat:
            self.report({'WARNING'}, "Material not supplied")
            return {"CANCELLED"}
        shader_path = utils.relative_path(mat.nwo.shader_path)
        full_path = Path(utils.get_tags_path(), shader_path)
        if not full_path.exists():
            self.report({'WARNING'}, "Tag not found")
            return {"CANCELLED"}
        tag_to_nodes(utils.is_corinth(context), mat, shader_path)
        return {"FINISHED"}
    
    def invoke(self, context: bpy.types.Context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "always_extract_bitmaps")

def tag_to_nodes(corinth: bool, mat: bpy.types.Material, tag_path: str, always_extract_bitmaps=False) -> set:
    """Turns a shader/material tag into blender material nodes"""
    print(f"--- Building material nodes for: {mat.name}")
    shader = None
    if corinth:
        with MaterialTag(path=tag_path) as shader:
            shader.to_nodes(mat, always_extract_bitmaps)
    else:
        shader_type = Path(tag_path).suffix[1:]
        match shader_type:
            case 'shader':
                with ShaderTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps)
            case 'shader_decal':
                with ShaderDecalTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps)
            case 'shader_terrain':
                with ShaderTerrainTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps)
            case 'shader_halogram':
                with ShaderHalogramTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps)
            case 'shader_foliage':
                with ShaderFoliageTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps)
            case 'shader_custom':
                with ShaderCustomTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps)
            case 'shader_glass':
                with ShaderGlassTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps)
            case 'shader_water':
                mat.use_nodes = True
                mat.node_tree.nodes.clear()
                output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
                group = mat.node_tree.nodes.new("ShaderNodeGroup")
                group.node_tree = utils.add_node_from_resources("shared_nodes", "Basic Water")
                group.location.x -= 300
                mat.node_tree.links.new(input=output.inputs[0], output=group.outputs[0])
    
    if shader is not None:
        mat.nwo.game_functions = ",".join(shader.game_functions)
        mat.nwo.object_functions = ",".join(shader.object_functions)
        if mat.node_tree is not None:
            arrange(mat.node_tree)
        return shader.sequence_drivers
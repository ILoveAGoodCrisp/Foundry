import os
from pathlib import Path
import time
import bpy

from .node_layout import layout_nodes
from ..tags.backend import read_only_tags
from ..tags.shader_glass import ShaderGlassTag
from ..tags.shader_custom import ShaderCustomTag
from ..tags.shader_halogram import ShaderHalogramTag
from ..tags.shader_foliage import ShaderFoliageTag
from ..tags.shader_terrain import ShaderTerrainTag
from ..tags.material import MaterialTag
from ..tags.shader_converter import ShaderTag, build_templates
from ..tags.shader_decal import ShaderDecalTag
from .. import utils

class NWO_OT_BuildShaderTemplates(bpy.types.Operator):
    bl_idname = "nwo.build_shader_templates"
    bl_label = "Generate Missing Shader Templates"
    bl_description = "Checks the in scope shaders for existing shader templates, where these are missing this tool will generate them"
    bl_options = {"UNDO"}
    
    scope: bpy.props.EnumProperty(
        name="Scope",
        items=[
            ("BLEND", "From Blend", "Runs only on shader paths set on materials in this blender file"),
            ("PATH", "File / Folder", "Runs on a specific shader tag or folders set here"),
            ("ALL", "All Shaders", "Runs on every single shader tag in your project tags directory")
        ]
    )
    
    path: bpy.props.StringProperty(
        name="Path",
        description="Path to a single shader of directory containing shaders. The path can be full or tag relative",
    )
    
    @classmethod
    def poll(cls, context):
        return utils.current_project_valid()
    
    def execute(self, context):
        
        shader_paths = []
        tags_path = utils.get_tags_path()
        
        utils.clear_output()
        scene_nwo_export = utils.get_export_props()
        if scene_nwo_export.show_output:
            utils.show_output()  # open Foundry Output so users can see progress
            
        print(f"Building Shader Templates\n")
        start = time.perf_counter()
        
        match self.scope:
            case 'BLEND':
                for mat in bpy.data.materials:
                    if not mat.nwo.RenderMaterial:
                        continue

                    shader_path = utils.relative_path(mat.nwo.shader_path)
                    full_path = Path(tags_path, shader_path)
                    if full_path.exists() and full_path.suffix in utils.shader_exts_reach:
                        shader_paths.append(shader_path)
            case 'PATH':
                if not self.path or len(self.path) < 3:
                    self.report({'WARNING'}, "No path supplied")
                    return  {"CANCELLED"}
                
                relative = utils.relative_path(self.path)
                full_path = Path(tags_path, relative)
                if not full_path.exists():
                    self.report({'WARNING'}, "Path does not exist")
                    return  {"CANCELLED"}
                
                if full_path.is_file() and full_path.suffix in utils.shader_exts_reach:
                    shader_paths = [relative]
                else:
                    for root, _, files in os.walk(full_path):
                        for file in files:
                            if file.endswith(utils.shader_exts_reach):
                                shader_paths.append(utils.relative_path(Path(root, file)))
                                
            case 'ALL':
                for root, _, files in os.walk(tags_path + os.sep):
                    for file in files:
                        if file.endswith(utils.shader_exts_reach):
                            shader_paths.append(utils.relative_path(Path(root, file)))
                        
        print(f"--- Found {len(shader_paths)} shader paths in scope")
        
        if len(shader_paths) == 0:
            self.report({'WARNING'}, "No shader paths in scope")
            return {"FINISHED"}
        
        new_template_count = build_templates(shader_paths, True)
        
        if new_template_count == 0:
            self.report({'INFO'}, "No new templates to build")
            return {"FINISHED"}
            
        end = time.perf_counter()
        plural = '' if new_template_count == 1 else 's'
        print("\n-----------------------------------------------------------------------")
        print(f"{new_template_count} template{plural} generated in {utils.human_time(end - start, True)}")
        print("-----------------------------------------------------------------------")
        self.report({'INFO'}, f"Built {new_template_count} new shader template{plural}")
        return {"FINISHED"}

    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scope", expand=True)
        if self.scope == 'PATH':
            layout.prop(self, "path")

class NWO_OT_ShaderToNodesBulk(bpy.types.Operator):
    bl_idname = "nwo.shader_to_nodes_bulk"
    bl_label = "Convert all Shaders to Blender Material Nodes"
    bl_description = "Builds blender materials for all shaders on local materials, skipping linked library materials"
    bl_options = {"UNDO"}
    
    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always extract bitmaps",
        description="By default existing tiff files will be used for shaders. Checking this option means the bitmaps will always be re-extracted regardless if they exist or not"
    )

    @classmethod
    def poll(cls, context):
        return utils.current_project_valid() and not utils.get_scene_props().export_in_progress
    
    def execute(self, context):
        corinth = utils.is_corinth(context)
        
        utils.clear_output()
        if utils.get_export_props().show_output:
            utils.show_output()  # open Foundry Output so users can see progress
        print(f"Building Blender Materials\n")
        
        built_count = 0
        linked_count = 0
        for mat in bpy.data.materials:
            if mat.library is not None:
                linked_count += 1
                continue
            if not mat.nwo.RenderMaterial:
                continue
            
            shader_path = utils.relative_path(mat.nwo.shader_path)
            full_path = Path(utils.get_tags_path(), shader_path)
            if not full_path.exists():
                continue
            
            tag_to_nodes(corinth, mat, shader_path)
            built_count += 1
            
        message = f"Built {built_count} blender materials"
        if linked_count:
            message += f"; skipped {linked_count} linked library materials"
        self.report({'INFO'}, message)
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
        return utils.current_project_valid() and not utils.get_scene_props().export_in_progress

    def execute(self, context):
        mat = bpy.data.materials.get(self.mat_name, 0)
        if not mat:
            self.report({'WARNING'}, "Material not supplied")
            return {"CANCELLED"}
        if mat.library is not None:
            self.report({'WARNING'}, "Linked library materials cannot be converted; edit the source blend file or make the material local")
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

@read_only_tags()
def tag_to_nodes(corinth: bool, mat: bpy.types.Material, tag_path: str, always_extract_bitmaps=False, *, target_game=None) -> set | None:
    """Turns a shader/material tag into blender material nodes"""

    # Linked materials belong to their source blend file. Even clearing their
    # node trees can affect their appearance for the rest of this session.
    if mat.library is not None:
        return
    
    if not Path(utils.get_tags_path(), utils.relative_path(tag_path)).exists():
        return
    
    print(f"--- Building material nodes for: {mat.name}")
    if 'foundry_material_conversion_error' in mat:
        del mat['foundry_material_conversion_error']
    shader = None
    if corinth:
        with MaterialTag(path=tag_path) as shader:
            shader.to_nodes(mat, always_extract_bitmaps, layout=False)
    else:
        shader_type = Path(tag_path).suffix[1:]
        match shader_type:
            case 'shader':
                with ShaderTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps, layout=False)
            case 'shader_decal':
                with ShaderDecalTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps, layout=False)
            case 'shader_terrain':
                with ShaderTerrainTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps, layout=False)
            case 'shader_halogram':
                with ShaderHalogramTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps, layout=False)
            case 'shader_foliage':
                with ShaderFoliageTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps, layout=False)
            case 'shader_custom':
                with ShaderCustomTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps, layout=False)
            case 'shader_glass':
                with ShaderGlassTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps, layout=False)
            case 'shader_water':
                mat.node_tree.nodes.clear()
                output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
                group = mat.node_tree.nodes.new("ShaderNodeGroup")
                group.node_tree = utils.add_node_from_resources("shared_nodes", "Basic Water")
                group.location.x -= 300
                mat.node_tree.links.new(input=output.inputs[0], output=group.outputs[0])
            case ('shader_model' | 'shader_environment' |
                  'shader_transparent_chicago' | 'shader_transparent_chicago_extended' |
                  'shader_transparent_generic' | 'shader_transparent_glass' |
                  'shader_transparent_meter' | 'shader_transparent_plasma' |
                  'shader_transparent_water'):
                with ShaderTag(path=tag_path) as shader:
                    shader.to_nodes(mat, always_extract_bitmaps, layout=False)
    
    if shader is not None:
        mat.nwo.set_shader_type(Path(shader.system_path).suffix, shader.game)
        mat.nwo.game_functions = ",".join(shader.game_functions)
        mat.nwo.object_functions = ",".join(shader.object_functions)
        if target_game is not None:
            from .material_game_mapping import GAME_LIBRARIES, convert_material_game
            converted = convert_material_game(mat, shader.game, target_game, layout=False)
            shared_library = (shader.game != target_game and target_game in GAME_LIBRARIES
                              and GAME_LIBRARIES.get(shader.game) == GAME_LIBRARIES[target_game])
            if converted or shared_library:
                # Keep provenance, but do not offer to overwrite a foreign
                # shader or accidentally resolve its relative path in this kit.
                mat['foundry_material_source_shader'] = str(shader.system_path)
                mat['foundry_material_source_game'] = shader.game
                mat['foundry_material_target_game'] = target_game
                mat.nwo['shader_path'] = ''
                mat.nwo.prev_shader_path = ''
                mat.nwo.material_shader = ''
                mat.nwo.uses_blender_nodes = True
                for node in mat.node_tree.nodes:
                    if node.type == 'GROUP' and node.node_tree is not None:
                        family = node.node_tree.name.partition('.')[2]
                        if family in {'shader', 'shader_custom', 'shader_decal', 'shader_foliage',
                                      'shader_glass', 'shader_halogram', 'shader_terrain'}:
                            mat.nwo.set_shader_type('.' + family, target_game)
                            break
        if mat.node_tree is not None:
            utils.update_foundry_material(mat, target_game or shader.game, arrange_nodes=False)
            layout_nodes(mat.node_tree)
        return shader.sequence_drivers
    if mat.node_tree is not None:
        utils.update_foundry_material(mat, target_game, arrange_nodes=False)
        layout_nodes(mat.node_tree)

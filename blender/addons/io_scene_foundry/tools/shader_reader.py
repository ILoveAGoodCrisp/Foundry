import multiprocessing
import os
from pathlib import Path
import time
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

class NWO_OT_BuildShaderTemplates(bpy.types.Operator):
    bl_idname = "nwo.build_shader_templates"
    bl_label = "Convert all Shaders to Blender Material Nodes"
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
        
        os.system("cls")
        if context.scene.nwo_export.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            
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
        
        new_template_count = 0
        processes = []
        max_process_count = multiprocessing.cpu_count()
        built_templates = set()
        
        print("--- Validating templates for shaders")
        for spath in shader_paths:
            with ShaderTag(path=spath) as shader:
                template = shader.tag.SelectField("Struct:render_method[0]/Block:postprocess[0]/Reference:shader template")
                if template is None:
                    continue
                template_path = shader.get_path_str(template.Path, True)
                if not template_path:
                    continue
                
                path_template = Path(template_path)
                if not path_template.exists():
                    definition = shader.definition
                    definition_path = shader.get_path_str(definition.Path, True)
                    if definition_path and Path(definition_path).exists():
                        template_name = path_template.with_suffix("").name
                        if template_name in built_templates:
                            continue
                        
                        built_templates.add(template_name)
                        
                        while len(processes) >= max_process_count:
                            processes = [p for p in processes if p.poll() is None]
                            time.sleep(0.1)
                        
                        print(f"--- Building template {template_name} for {spath}")
                        new_template_count += 1
                        processes.append(utils.run_tool(["generate-specified-template", "win", definition.Path.RelativePath, template_name], in_background=True, null_output=True))
                        
        if new_template_count == 0:
            self.report({'INFO'}, "No new templates to build")
            return {"FINISHED"}
        
        print(f"--- Waiting for Tool processes to complete")
        for p in processes:
            p.wait()
            
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
    bl_description = "Builds blender materials for all shaders"
    bl_options = {"UNDO"}
    
    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always extract bitmaps",
        description="By default existing tiff files will be used for shaders. Checking this option means the bitmaps will always be re-extracted regardless if they exist or not"
    )

    @classmethod
    def poll(cls, context):
        return utils.current_project_valid() and not context.scene.nwo.export_in_progress
    
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
        return utils.current_project_valid() and not context.scene.nwo.export_in_progress

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
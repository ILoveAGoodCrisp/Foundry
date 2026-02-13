
from pathlib import Path
import bpy
import os
from ..managed_blam.shader import ShaderTag
from ..managed_blam.material import MaterialTag
from .. import utils

global_material_shaders = []
material_shader_path = ""

def build_shader(material, corinth, folder="", report=None):
    asset_dir = utils.get_asset_path()
    if not utils.get_shader_name(material):
        return {"FINISHED"}
    if material.name != material.name_full:
        print(f"{material.name} is linked, skipping")
        return {"FINISHED"}
    nwo = material.nwo
    if utils.material_read_only(nwo.shader_path):
        print(f"{material.name} is read only, skipping")
        return {'FINISHED'}
    if nwo.shader_path.strip():
        shader_path = Path(nwo.shader_path)
    else:
        if folder:
            shader_dir = folder
        else:
            if utils.is_corinth():
                shader_dir = Path(asset_dir, "materials")
            else:
                shader_dir = Path(asset_dir, "shaders")
                
        shader_name = utils.get_shader_name(material)
        shader_path = Path(shader_dir, shader_name)
        
    if not shader_path.suffix:
        shader_path = shader_path.with_suffix("")
        
    if corinth:
        with MaterialTag(path=shader_path.with_suffix(".material")) as tag:
            nwo.shader_path = tag.write_tag(material, nwo.uses_blender_nodes, material_shader=nwo.material_shader)
    else:
        with ShaderTag(path=shader_path.with_suffix(".shader")) as tag:
            nwo.shader_path = tag.write_tag(material, nwo.uses_blender_nodes)
        if report is not None:
            report({'INFO'}, f"Created Shader Tag for {material.name}")

    return {"FINISHED"}

class NWO_ListMaterialShaders(bpy.types.Operator):
    bl_idname = "nwo.get_material_shaders"
    bl_label = "Get Material Shaders"
    bl_options = {"UNDO"}
    bl_property = "shader_info"
    batch_instance = None

    batch_panel : bpy.props.BoolProperty(options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material and utils.is_corinth(context)
    
    def shader_info_items(self, context):
        global global_material_shaders
        if global_material_shaders:
            return global_material_shaders
        items = []
        tags_dir = utils.get_tags_path()
        shaders_dir = str(Path(tags_dir, "shaders", "material_shaders"))
        material_shaders = []
        # walk shaders dir and collect
        for root, _, files in os.walk(shaders_dir):
            for file in files:
                if file.endswith(".material_shader"):
                    material_shaders.append(os.path.join(root, file).replace(tags_dir + os.sep, ""))
        
        # Order so we get shaders in the materials folder first
        ordered_shaders = sorted(material_shaders, key=lambda s: (0, s) if s.startswith(r"shaders\material_shaders\materials") else (1, s))

        for ms in ordered_shaders:
            items.append((ms, utils.dot_partition(utils.os_sep_partition(ms, True)), ""))

        return items
    
    shader_info : bpy.props.EnumProperty(
        name="Type",
        items=shader_info_items,
    )

    def execute(self, context: bpy.types.Context):
        if self.batch_panel:
            global material_shader_path
            material_shader_path = self.shader_info
        else:
            context.object.active_material.nwo.material_shader = self.shader_info
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {"FINISHED"}

class NWO_Shader_BuildSingle(bpy.types.Operator):
    bl_idname = "nwo.build_shader_single"
    bl_label = ""
    bl_options = {"UNDO"}
    bl_description = ""

    linked_to_blender : bpy.props.BoolProperty()

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material and not utils.protected_material_name(context.object.active_material.name)
    
    def execute(self, context):
        with utils.ExportManager():
            nwo = context.object.active_material.nwo
            nwo.uses_blender_nodes = self.linked_to_blender
            return build_shader(
                context.object.active_material,
                utils.is_corinth(context),
                report=self.report,
            )
    
    @classmethod
    def description(cls, context, properties) -> str:
        tag_type = 'material' if utils.is_corinth(context) else 'shader'
        if properties.linked_to_blender:
            return f"Creates an linked {tag_type} tag for this material. The tag will populate using Blender Material Nodes"
        else:
            return f"Creates an empty {tag_type} tag for this material"


class NWO_ShaderPropertiesGroup(bpy.types.PropertyGroup):
    update: bpy.props.BoolProperty(
        name="Update",
        description="Enable to overwrite already existing asset shaders",
        options=set(),
    )
    material_selection: bpy.props.EnumProperty(
        name="Selection",
        default="active",
        description="Choose whether to build a shader for the active material, or build shaders for all appropriate materials",
        options=set(),
        items=[
            (
                "active",
                "Active",
                "Build a shader for the active material only",
            ),
            ("all", "All", "Builds shaders for all appropriate materials"),
        ],
    )      
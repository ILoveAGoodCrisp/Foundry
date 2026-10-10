
from pathlib import Path
import bpy
import os

from ..tags.shader import EmptyShaderTag
from ..tags.shader_converter import ShaderTag, build_templates
from ..tags.shader_custom import ShaderCustomTag
from ..tags.shader_decal import ShaderDecalTag
from ..tags.shader_foliage import ShaderFoliageTag
from ..tags.shader_glass import ShaderGlassTag
from ..tags.shader_halogram import ShaderHalogramTag
from ..tags.shader_terrain import ShaderTerrainTag
from ..tags.shader_specialized import (ShaderCortanaTag, ShaderSkinTag, ShaderWaterTag,
    ShaderFurTag, ShaderFurStencilTag, ShaderMuxTag, ShaderMuxMaterialTag, ShaderScreenTag)
from ..tags.material import MaterialTag
from .. import utils

global_material_shaders = []
material_shader_path = ""

REACH_GROUP_TO_CLASS = {
    "foundry_reach.shader": (ShaderTag, ".shader"),
    "foundry_reach.shader_custom": (ShaderCustomTag, ".shader_custom"),
    "foundry_reach.shader_decal": (ShaderDecalTag, ".shader_decal"),
    "foundry_reach.shader_foliage": (ShaderFoliageTag, ".shader_foliage"),
    "foundry_reach.shader_glass": (ShaderGlassTag, ".shader_glass"),
    "foundry_reach.shader_halogram": (ShaderHalogramTag, ".shader_halogram"),
    "foundry_reach.shader_terrain": (ShaderTerrainTag, ".shader_terrain"),
}

REACH_SUFFIX_TO_CLASS = {
    ".shader_cortana": (ShaderCortanaTag, ".shader_cortana"),
    ".shader_skin": (ShaderSkinTag, ".shader_skin"),
    ".shader_water": (ShaderWaterTag, ".shader_water"),
    ".shader": (ShaderTag, ".shader"),
    ".shader_custom": (ShaderCustomTag, ".shader_custom"),
    ".shader_decal": (ShaderDecalTag, ".shader_decal"),
    ".shader_foliage": (ShaderFoliageTag, ".shader_foliage"),
    ".shader_glass": (ShaderGlassTag, ".shader_glass"),
    ".shader_halogram": (ShaderHalogramTag, ".shader_halogram"),
    ".shader_terrain": (ShaderTerrainTag, ".shader_terrain"),
}

# H3 groups must determine the specialized tag type even for a new path.
REACH_GROUP_TO_CLASS.update({
    prefix + suffix: value for prefix in ('foundry_h3', 'foundry_h3odst')
    for suffix, value in REACH_SUFFIX_TO_CLASS.items()
    if suffix != '.shader_glass'
})

# Reach-only families must not be advertised as H3 entry groups.
REACH_SUFFIX_TO_CLASS.update({
    '.'+cls.tag_ext:(cls,'.'+cls.tag_ext)
    for cls in (ShaderFurTag,ShaderFurStencilTag,ShaderMuxTag,ShaderMuxMaterialTag,ShaderScreenTag)
})
REACH_GROUP_TO_CLASS.update({'foundry_reach'+suffix:value for suffix,value in REACH_SUFFIX_TO_CLASS.items()})


def _normalize_group_name(name: str) -> str:
    if not name:
        return ""

    normalized = name.lower().replace(" ", "_")
    # Blender appends numeric copy suffixes like ".001" to datablock names.
    # Strip only numeric suffixes so semantic shader suffixes (e.g. ".shader")
    # remain available for class routing.
    base, sep, suffix = normalized.rpartition(".")
    if sep and suffix.isdigit():
        return base
    return normalized


def _material_output_group(material: bpy.types.Material):
    node_tree = getattr(material, "node_tree", None)
    if node_tree is None:
        return None
    output = next((node for node in node_tree.nodes if node.type == "OUTPUT_MATERIAL"), None)
    if output is None or not output.inputs[0].links:
        return None
    group_node = output.inputs[0].links[0].from_node
    if group_node.type != "GROUP" or group_node.node_tree is None:
        return None
    return group_node


def _resolve_reach_shader_class(material: bpy.types.Material, shader_path: Path, shader_type: str):
    group_node = _material_output_group(material)
    if group_node is not None:
        group_name = _normalize_group_name(group_node.node_tree.name)
        match = REACH_GROUP_TO_CLASS.get(group_name)
        if match is not None:
            return match

    suffix = shader_path.suffix.lower()
    if suffix in REACH_SUFFIX_TO_CLASS:
        return REACH_SUFFIX_TO_CLASS[suffix]

    if shader_type:
        explicit = shader_type.lower()
        if not explicit.startswith("."):
            explicit = "." + explicit
        if explicit in REACH_SUFFIX_TO_CLASS:
            return REACH_SUFFIX_TO_CLASS[explicit]

    return REACH_SUFFIX_TO_CLASS[".shader"]

def build_shader(material, corinth, folder="", report=None):
    conversion_error = material.get('foundry_material_conversion_error')
    if conversion_error:
        message = f'{material.name}: material conversion is incomplete: {conversion_error}. Reimport the material before building its shader'
        utils.print_warning(message)
        if report:
            report({'WARNING'}, message)
        return {'CANCELLED'}
    asset_dir = utils.get_asset_path()
    if not utils.get_shader_name(material):
        return {"FINISHED"}
    if material.name != material.name_full:
        print(f"{material.name} is linked, skipping")
        return {"FINISHED"}
    nwo = material.nwo
    project = utils.get_project(utils.get_scene_props().scene_project)
    game = project.game if project else 'reach'
    shader_type = nwo.get_shader_type(game)
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
        
    if game == 'halo1':
        suffix = shader_type
        if suffix == 'auto':
            suffix = '.shader_environment' if utils.get_scene_props().asset_type == 'scenario' else '.shader_model'
            if nwo.uses_blender_nodes:
                group = _material_output_group(material)
                if group is not None:
                    group_name = _normalize_group_name(group.node_tree.name)
                    if group_name.startswith('foundry_h1.shader_') and not group_name.endswith('_vector'):
                        suffix = '.' + group_name.partition('.')[2]
                if shader_path.suffix.lower() in {'.shader_model', '.shader_environment',
                        '.shader_transparent_generic', '.shader_transparent_chicago',
                        '.shader_transparent_chicago_extended', '.shader_transparent_glass',
                        '.shader_transparent_meter', '.shader_transparent_plasma', '.shader_transparent_water'}:
                    suffix = shader_path.suffix.lower()
        tag_class = ShaderTag if nwo.uses_blender_nodes else EmptyShaderTag
        try:
            with tag_class(path=shader_path.with_suffix(suffix), tag_must_exist=False) as tag:
                path = (tag.write_tag(material, True) if nwo.uses_blender_nodes
                        else tag.tag_path.RelativePathWithExtension)
            nwo.shader_path = path
        except ValueError as exc:
            if report is None:
                raise
            report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        if report is not None:
            report({'INFO'}, f"Created Shader Tag for {material.name}")
    elif game == 'halo2':
        tag_class = ShaderTag if nwo.uses_blender_nodes else EmptyShaderTag
        try:
            with tag_class(path=shader_path.with_suffix('.shader'), tag_must_exist=False) as tag:
                nwo.shader_path = (tag.write_tag(material, True) if nwo.uses_blender_nodes
                                  else tag.tag_path.RelativePathWithExtension)
        except ValueError as exc:
            if report is None:
                raise
            report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        if report is not None:
            report({'INFO'}, f"Created Shader Tag for {material.name}")
    elif corinth:
        with MaterialTag(path=shader_path.with_suffix(".material"), tag_must_exist=False) as tag:
            nwo.shader_path = tag.write_tag(material, nwo.uses_blender_nodes, material_shader=nwo.material_shader)
    else:
        if nwo.uses_blender_nodes:
            tag_class, suffix = _resolve_reach_shader_class(material, shader_path, shader_type)
            with tag_class(path=shader_path.with_suffix(suffix), tag_must_exist=False) as tag:
                nwo.shader_path = tag.write_tag(material, nwo.uses_blender_nodes)
        else:
            # Initialize modern shaders with their default definition/options so
            # their template can be generated even without Blender node export.
            tag_class = REACH_SUFFIX_TO_CLASS.get(shader_type, (EmptyShaderTag,))[0]
            with tag_class(path=shader_path.with_suffix(shader_type),
                           tag_must_exist=False) as tag:
                from ..tags.texture_camera import write_texture_camera_source
                write_texture_camera_source(tag, nwo.texture_camera_parameter, nwo.use_texture_camera)
                nwo.shader_path = tag.tag_path.RelativePathWithExtension
                
        if nwo.shader_path:
            build_templates([nwo.shader_path], from_options=True)
        
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
        if not utils.poll_project(cls):
            return False
        return context.object and context.object.active_material and utils.is_corinth(context)
    
    def shader_info_items(self, context):
        if not utils.current_project_valid():
            return []
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
        if not utils.require_project(self):
            return {'CANCELLED'}
        if self.batch_panel:
            global material_shader_path
            material_shader_path = self.shader_info
        else:
            context.object.active_material.nwo.material_shader = self.shader_info
        return {"FINISHED"}

    def invoke(self, context, event):
        if not utils.require_project(self):
            return {'CANCELLED'}
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
        return utils.current_project_valid() and context.object and context.object.active_material and utils.has_shader_path(context.object.active_material)
    
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
        h4 = utils.is_corinth(context)
        tag_type = 'material' if h4 else 'shader'
        project = utils.get_project(utils.get_scene_props().scene_project)
        added_bit = ("" if h4 or (project and project.game == 'halo1') else
                     ". Ignores the set shader type, instead using blender shader nodes to determine the type")
        if properties.linked_to_blender:
            return f"Creates a linked {tag_type} tag for this material. The tag will populate using Blender Material Nodes{added_bit}"
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

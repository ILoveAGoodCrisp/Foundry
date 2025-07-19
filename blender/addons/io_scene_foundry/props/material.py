from pathlib import Path
import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty

from .mesh import NWO_FaceProperties_ListItems
from .. import utils
from ..tools.materials import special_materials, convention_materials


class NWO_MaterialPropertiesGroup(PropertyGroup):
    def update_shader(self, context):
        self["shader_path"] = utils.clean_tag_path(self["shader_path"])
        shader_path = self.shader_path
        full_path = Path(utils.get_tags_path(), shader_path)
        if utils.get_prefs().update_materials_on_shader_path and self.prev_shader_path != self.shader_path and full_path.exists() and bpy.ops.nwo.shader_to_nodes.poll():
            bpy.ops.nwo.shader_to_nodes(mat_name=self.id_data.name)
            
        self.prev_shader_path = self.shader_path

    shader_path: StringProperty(
        name="Shader Path",
        description="The path to a shader. This can either be a relative path, or if you have added your Editing Kit Path to add on preferences, the full path. Include the file extension as this will set the shader/material type",
        update=update_shader,
        options=set(),
    )
    
    prev_shader_path: StringProperty(options={'HIDDEN'})
    
    material_props: bpy.props.CollectionProperty(
        type=NWO_FaceProperties_ListItems, override={"USE_INSERTION"}
    )
    
    material_props_active_index: bpy.props.IntProperty(
        name="Index for Material Property",
        options=set(),
    )
    
    def get_material_props_allowed(self):
        return not self.SpecialMaterial and not self.ConventionMaterial
    
    material_props_allowed: bpy.props.BoolProperty(
        options={'HIDDEN'},
        get=get_material_props_allowed,
    )

    def recursive_image_search_object(self, tree_owner, object):
        nodes = tree_owner.node_tree.nodes
        for n in nodes:
            if getattr(n, "image", 0):
                if n.image == object:
                    return True
            elif n.type == 'GROUP':
                image_found = self.recursive_image_search_object(n, object)
                if image_found:
                    return True

    def poll_active_image(self, object):
        mat = bpy.context.object.active_material
        return self.recursive_image_search_object(mat, object)

    active_image : bpy.props.PointerProperty(
        type=bpy.types.Image,
        poll=poll_active_image,
        )
    
    def update_material_shader(self, context):
        self["material_shader"] = utils.clean_tag_path(self["material_shader"]).strip('"')

    material_shader : StringProperty(
        name="Material Shader",
        description="Tag relative path to a material shader. Generated material tag will use this material shader. Leave blank to let the material exporter choose the best material_shader based on the current material node setup",
        options=set(),
        update=update_material_shader,
    )

    shader_type_items = [
        (".shader", "Default", ""),
        (".shader_cortana", "Cortana", ""),
        (".shader_custom", "Custom", ""),
        (".shader_decal", "Decal", ""),
        (".shader_foliage", "Foliage", ""),
        (".shader_fur", "Fur", ""),
        (".shader_fur_stencil", "Fur Stencil", ""),
        (".shader_glass", "Glass", ""),
        (".shader_halogram", "Halogram", ""),
        (".shader_mux", "Mux", ""),
        (".shader_mux_material", "Mux Material", ""),
        (".shader_screen", "Screen", ""),
        (".shader_skin", "Skin", ""),
        (".shader_terrain", "Terrain", ""),
        (".shader_water", "Water", ""),
    ]

    shader_type : bpy.props.EnumProperty(
        name="Shader Type",
        description="Type of shader to generate",
        items=shader_type_items,
        options=set(),
    )

    uses_blender_nodes : BoolProperty(
        name="Uses Blender Nodes",
        description="Allow tag to be updated from Blender Shader nodes",
        options=set(),
    )
    
    
    game_functions: bpy.props.StringProperty(options={'HIDDEN'}) # comma delimited list of functions for this shader
    object_functions: bpy.props.StringProperty(options={'HIDDEN'})
    sequence_drivers: bpy.props.StringProperty(options={'HIDDEN'})
    
    def get_special_material(self):
        material_name: str = self.id_data.name
        return material_name.startswith(tuple([m.name for m in special_materials]))
    
    SpecialMaterial: BoolProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_special_material,
    )
    
    def get_convention_material(self):
        material_name: str = self.id_data.name
        return material_name.startswith(tuple([m.name for m in convention_materials]))
    
    ConventionMaterial: BoolProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_convention_material,
    )
    
    def get_render_material(self):
        return not (self.id_data.is_grease_pencil or self.SpecialMaterial or self.ConventionMaterial)
    
    RenderMaterial: BoolProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_render_material,
    )
    
    emits: BoolProperty(options={'HIDDEN'})
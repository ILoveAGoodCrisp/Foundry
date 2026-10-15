from pathlib import Path
import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty

from .mesh import NWO_FaceProperties_ListItems
from .. import utils
from ..tools.materials import special_materials, convention_materials


MODERN_SHADER_TYPES = (
    'shader', 'shader_cortana', 'shader_custom', 'shader_decal', 'shader_foliage',
    'shader_fur', 'shader_fur_stencil', 'shader_glass', 'shader_halogram',
    'shader_mux', 'shader_mux_material', 'shader_screen', 'shader_skin',
    'shader_terrain', 'shader_water',
)
SHADER_TYPES_BY_GAME = {
    'halo1': ('auto', 'shader_model', 'shader_environment',
              'shader_transparent_generic', 'shader_transparent_chicago',
              'shader_transparent_chicago_extended', 'shader_transparent_glass',
              'shader_transparent_meter', 'shader_transparent_plasma', 'shader_transparent_water'),
    'halo2': ('shader',),
    'halo3': tuple(kind for kind in MODERN_SHADER_TYPES if kind not in {
        'shader_fur', 'shader_fur_stencil', 'shader_glass', 'shader_mux',
        'shader_mux_material', 'shader_screen'}),
    'halo3odst': tuple(kind for kind in MODERN_SHADER_TYPES if kind not in {
        'shader_fur', 'shader_fur_stencil', 'shader_glass', 'shader_mux', 'shader_mux_material'}) + ('shader_black',),
    'reach': MODERN_SHADER_TYPES,
    'halo4': ('material',),
    'halo2a': ('material',),
}


def _shader_type_getter(property_name, identifiers):
    def get(self):
        if property_name in self:
            return self[property_name]
        # Preserve the old shared enum's saved selection when valid for this game.
        legacy = self.shader_type
        return identifiers.index(legacy) if legacy in identifiers else 0
    return get


def _shader_type_setter(property_name):
    def set(self, value):
        self[property_name] = value
    return set


class NWO_MaterialPropertiesGroup(PropertyGroup):
    use_texture_camera: BoolProperty(
        name="Texture Camera Feed", default=False, options=set(),
        description="Display the live game texture-camera feed through a shader bitmap input",
    )
    texture_camera_parameter: StringProperty(
        name="Feed Parameter", default="self_illum_map", options=set(),
        description="Shader bitmap input names to replace with the live camera feed, separated by commas",
    )

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
        options={'HIDDEN'},
    )

    for game, types in SHADER_TYPES_BY_GAME.items():
        property_name = 'shader_type_' + game
        identifiers = tuple(kind if kind == 'auto' else '.' + kind for kind in types)
        __annotations__[property_name] = bpy.props.EnumProperty(
            name="Shader Type",
            description="Type of shader to generate for this game",
            items=[(identifier, 'Default' if kind in {'auto', 'shader'} else
                    kind.removeprefix('shader_').replace('_', ' ').title(),
                    'Environment for scenarios, model for other assets' if kind == 'auto' else '')
                   for identifier, kind in zip(identifiers, types)],
            get=_shader_type_getter(property_name, identifiers),
            set=_shader_type_setter(property_name),
            options=set(),
        )

    def shader_type_property(self, game=None):
        if game is None:
            project = utils.get_project(utils.get_scene_props().scene_project)
            game = project.game if project else 'reach'
        return 'shader_type_' + game

    def get_shader_type(self, game=None):
        return getattr(self, self.shader_type_property(game))

    def set_shader_type(self, value, game=None):
        property_name = self.shader_type_property(game)
        if value in self.bl_rna.properties[property_name].enum_items.keys():
            setattr(self, property_name, value)

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
    
    # emits: BoolProperty(options={'HIDDEN'})

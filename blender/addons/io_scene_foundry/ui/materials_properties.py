# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
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

from math import radians
import os
from pathlib import Path
import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty
from io_scene_foundry.utils.nwo_utils import clean_tag_path, get_asset_path, get_prefs, get_tags_path, is_corinth, valid_nwo_asset
from io_scene_foundry.utils.nwo_materials import special_materials, convention_materials


class NWO_MaterialPropertiesGroup(PropertyGroup):
    def update_shader(self, context):
        self["shader_path"] = clean_tag_path(self["shader_path"])
        shader_path = self.shader_path
        full_path = Path(get_tags_path(), shader_path)
        if get_prefs().update_materials_on_shader_path and self.prev_shader_path != self.shader_path and full_path.exists() and bpy.ops.nwo.shader_to_nodes.poll():
            bpy.ops.nwo.shader_to_nodes(mat_name=self.id_data.name)
            
        self.prev_shader_path = self.shader_path

    shader_path: StringProperty(
        name="Shader Path",
        description="The path to a shader. This can either be a relative path, or if you have added your Editing Kit Path to add on preferences, the full path. Include the file extension as this will set the shader/material type",
        update=update_shader,
        options=set(),
    )
    
    prev_shader_path: StringProperty()

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
        self["material_shader"] = clean_tag_path(self["material_shader"]).strip('"')

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
    
    # Export Material props
    
    
    # LE MATERIAL PROPERTIES
    
            
    # def update_lighting_attenuation_falloff(self, context):
    #     if not context.scene.nwo.transforming:
    #         if self.material_lighting_attenuation_falloff_ui > self.material_lighting_attenuation_cutoff_ui:
    #             self.material_lighting_attenuation_cutoff_ui = self.material_lighting_attenuation_falloff_ui
            
    # def update_lighting_attenuation_cutoff(self, context):
    #     if not context.scene.nwo.transforming:
    #         if self.material_lighting_attenuation_cutoff_ui < self.material_lighting_attenuation_falloff_ui:
    #             self.material_lighting_attenuation_falloff_ui = self.material_lighting_attenuation_cutoff_ui
    
    # emissive_attenuation_cutoff_ui: bpy.props.FloatProperty(
    #     name="Light Cutoff",
    #     options=set(),
    #     description="Determines how far light travels before it stops. Leave this at 0 to for realistic light falloff/cutoff",
    #     min=0,
    #     default=0,
    #     update=update_lighting_attenuation_cutoff,
    #     subtype='DISTANCE',
    #     unit='LENGTH',
    # )

    # emissive_attenuation_falloff_ui: bpy.props.FloatProperty(
    #     name="Light Falloff",
    #     options=set(),
    #     description="Determines how far light travels before its power begins to falloff",
    #     min=0,
    #     default=0,
    #     update=update_lighting_attenuation_falloff,
    #     subtype='DISTANCE',
    #     unit='LENGTH',
    # )

    # emissive_focus_ui: bpy.props.FloatProperty(
    #     name="Material Lighting Emissive Focus",
    #     options=set(),
    #     description="Controls the spread of the light. 180 degrees will emit light in a hemisphere from each point, 0 degrees will emit light nearly perpendicular to the surface",
    #     min=0,
    #     default=radians(180), 
    #     max=radians(180),
    #     subtype="ANGLE",
    # )

    # emissive_color_ui: bpy.props.FloatVectorProperty(
    #     name="Emissive Color",
    #     options=set(),
    #     description="The RGB value of the emitted light",
    #     default=(1.0, 1.0, 1.0),
    #     subtype="COLOR",
    #     min=0.0,
    #     max=1.0,
    # )

    # emissive_per_unit_ui: BoolProperty(
    #     name="Emissive Per Unit",
    #     options=set(),
    #     description="When an emissive surface is scaled, determines if the amount of emitted light should be spread out across the surface or increased/decreased to keep a regular amount of light emission per unit area",
    #     default=False,
    # )

    # emissive_power_ui: bpy.props.FloatProperty(
    #     name="Emissive Power",
    #     options=set(),
    #     description="The intensity of this light",
    #     min=0,
    #     default=0,
    # )

    # emissive_quality_ui: bpy.props.FloatProperty(
    #     name="Emissive Quality",
    #     options=set(),
    #     description="Controls the quality of the shadows cast by a complex occluder. For instance, a light casting shadows of tree branches on a wall would require a higher quality to get smooth shadows",
    #     default=1,
    #     min=0,
    # )

    # emissive_use_shader_gel_ui: BoolProperty(
    #     name="Use Shader Gel",
    #     options=set(),
    #     description="Only emits light from the parts of a shader/material which have self-illumination",
    #     default=False,
    # )

    # emissive_bounce_ratio_ui: bpy.props.FloatProperty(
    #     name="Lighting Bounce Ratio",
    #     options=set(),
    #     description="0 will bounce no energy. 1 will bounce full energy. Any value greater than 1 will exaggerate the amount of bounced light. Affects 1st bounce only",
    #     default=1,
    #     min=0,
    # )
    

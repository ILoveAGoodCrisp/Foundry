# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
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

import os
import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty
from io_scene_foundry.utils.nwo_utils import clean_tag_path, get_asset_path, get_prefs, get_tags_path, is_corinth, valid_nwo_asset


class NWO_MaterialPropertiesGroup(PropertyGroup):
    def update_shader(self, context):
        self["shader_path"] = clean_tag_path(self["shader_path"]).strip('"')
        if get_prefs().update_materials_on_shader_path and bpy.ops.nwo.shader_to_nodes.poll():
            bpy.ops.nwo.shader_to_nodes(mat_name=self.id_data.name)

    shader_path: StringProperty(
        name="Shader Path",
        description="Define the path to a shader. This can either be a relative path, or if you have added your Editing Kit Path to add on preferences, the full path. Include the file extension as this will set the shader/material type",
        update=update_shader,
        options=set(),
    )

    rendered: BoolProperty(default=True)

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
    
    def update_shader_dir(self, context):
        self["shader_dir"] = clean_tag_path(self["shader_dir"]).strip('"')

    def get_shader_dir(self):
        context = bpy.context
        is_asset = valid_nwo_asset(context)
        if is_asset:
            return self.get("shader_dir", os.path.join(get_asset_path(), "materials" if is_corinth(context) else "shaders"))
        return self.get("shader_dir", "")
    
    def set_shader_dir(self, value):
        self['shader_dir'] = value

    shader_dir : StringProperty(
        name="Export Directory",
        description="Specifies the directory to export this Material. Defaults to the asset materials/shaders folder",
        options=set(),
        update=update_shader_dir,
        get=get_shader_dir,
        set=set_shader_dir,
    )
    
    # Export Material props
    
    
    # LE MATERIAL PROPERTIES
    
    # face_sides: bpy.props.EnumProperty()
    # collision_type: bpy.props.EnumProperty()
    

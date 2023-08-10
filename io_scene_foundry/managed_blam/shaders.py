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

from io_scene_foundry.managed_blam import ManagedBlam
from io_scene_foundry.utils.nwo_utils import dot_partition, get_asset_path, get_valid_shader_name
import os
import bpy


class ManagedBlamNewShader(ManagedBlam):
    def __init__(self, blender_material, is_reach, shader_type):
        super().__init__()
        self.blender_material = blender_material
        self.is_reach = is_reach
        self.shader_type = shader_type
        self.tag_helper()

    def get_path(self):
        asset_path = get_asset_path()
        shaders_dir = os.path.join(asset_path, "shaders" if self.is_reach else "materials")
        shader_name = get_valid_shader_name(self.blender_material)
        tag_ext = self.shader_type if self.is_reach else ".material"
        shader_path = os.path.join(shaders_dir, shader_name + tag_ext)

        return shader_path

    def tag_edit(self, tag):
        # Get diffuse input
        self.set_maps()
        if self.is_reach:
            self.shader_tag_edit(tag)
        else:
            self.material_tag_edit(tag)

    def shader_tag_edit(self, tag):
        struct_render_method = tag.SelectField("Struct:render_method").Elements[0]
        if self.shader_type == ".shader":
            # Set up shader options
            block_options = struct_render_method.SelectField("options")
            # Set albedo to default
            self.field_set_value_by_name(block_options.Elements[0], "short", "0")
            # Set bump_mapping to standard
            self.field_set_value_by_name(block_options.Elements[1], "short", "1")
            # Set up shader parameters
            block_parameters = struct_render_method.SelectField("parameters")
            block_parameters.RemoveAllElements()
            if self.diffuse_map:
                new_element = block_parameters.AddElement()
                self.field_set_value_by_name(new_element, "parameter name", "base_map")
                self.field_set_value_by_name(new_element, "parameter type", "bitmap")
                self.field_set_value_by_name(new_element, "bitmap", self.diffuse_map)
                self.field_set_value_by_name(new_element, "bitmap flags", "1") # sets override
                self.field_set_value_by_name(new_element, "bitmap filter mode", "6") # sets anisotropic (4) EXPENSIVE


    def material_tag_edit(self, tag):
        if not self.shader_type:
            self.shader_type = r"shaders\material_shaders\materials\srf_ward.material_shader"
        reference_material_shader = tag.SelectField("Reference:material shader")
        reference_material_shader.Reference.Path = self.TagPath_from_string(self.shader_type)
        block_material_parameters = tag.SelectField("Block:material parameters")
        block_material_parameters.RemoveAllElements()
        if self.diffuse_map:
            new_element = block_material_parameters.AddElement()
            self.field_set_value_by_name(new_element, "parameter name", "color_map")
            self.field_set_value_by_name(new_element, "parameter type", "bitmap")
            self.field_set_value_by_name(new_element, "bitmap", self.diffuse_map)
            # field_set_value_by_name(new_element, "bitmap path", r"shaders/default_bitmaps/bitmaps/default_diff.tif")
            self.field_set_value_by_name(new_element, "bitmap flags", "1") # sets override
            self.field_set_value_by_name(new_element, "bitmap filter mode", "6") # sets anisotropic (4) EXPENSIVE

    def set_maps(self):
        node_tree = bpy.data.materials[self.blender_material].node_tree
        shader_node = self.get_blender_shader(node_tree)
        self.diffuse_map = self.get_diffuse_map(shader_node)

    def get_blender_shader(self, node_tree):
        output = None
        shaders = []
        for node in node_tree.nodes:
            if node.type == "OUTPUT_MATERIAL":
                output = node
            elif node.type.startswith("BSDF"):
                shaders.append(node)
        # Get the shader plugged into the output
        if output is None:
            print("Material has no output")
            return
        for s in shaders:
            if s.outputs[0].links[0].to_node == output:
                return s
        else:
            print("No shader found connected to output")
            return

    def get_diffuse_map(self, shader):
        color_input = None
        image_node = None
        bitmap = None
        for i in shader.inputs:
            if i.name.lower().endswith("color"):
                color_input = i
                if color_input.links:
                    break
                else:
                    return
        else:
            return
        
        if color_input.links[0].from_node.type == 'TEX_IMAGE':
            image_node = color_input.links[0].from_node
        else:
            return
        
        image = image_node.image
        nwo = image.nwo
        if nwo.filepath:
            bitmap = dot_partition(nwo.filepath) + ".bitmap"
        elif image.filepath:
            bitmap = dot_partition(image.filepath.replace(self.data_dir, "")) + ".bitmap"
        else:
            print("No Tiff path")

        if os.path.exists(self.tags_dir + bitmap):
            return bitmap
        
        print("Bitmap does not exist")
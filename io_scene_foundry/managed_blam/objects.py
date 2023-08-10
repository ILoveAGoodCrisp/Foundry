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
from io_scene_foundry.managed_blam import ManagedBlam


class ManagedBlamGetNodeOrder(ManagedBlam):
    def __init__(self, tag_path, is_animation_graph=False):
        super().__init__()
        self.read_only = True
        self.path = tag_path
        self.is_anim_graph = is_animation_graph
        self.tag_helper()
    
    def tag_read(self, tag):
        self.nodes = []
        if self.is_anim_graph:
            nodes_block = tag.SelectField("Struct:definitions[0]/Block:skeleton nodes")
        else:
            nodes_block = tag.SelectField("Block:nodes")

        for element in nodes_block:
            node_name = element.SelectField("name").GetStringData()
            self.nodes.append(node_name)

class ManagedBlamGetModelFromObject(ManagedBlam):
    def __init__(self, tag_path):
        super().__init__()
        self.read_only = True
        self.path = tag_path
        self.tag_helper()
    
    def tag_read(self, tag):
        # Find the object struct
        first_struct = tag.Fields[0]
        if first_struct.DisplayName == "object":
            object_struct = first_struct
        else:
            object_struct = first_struct.Elements[0].Fields[0]

        model_field = tag.SelectField(f"{object_struct.FieldPath}/Reference:model")
        model_path = model_field.Path
        if model_path:
            self.model_tag_path = model_path.RelativePathWithExtension
        else:
            print(f"{self.path} has no model reference")
            self.model_tag_path = None

class ManagedBlamGetModelVariants(ManagedBlam):
    def __init__(self, tag_path):
        super().__init__()
        self.read_only = True
        self.path = tag_path
        self.tag_helper()
    
    def tag_read(self, tag):
        self.variants = []
        # Select the variants block
        variants_block = tag.SelectField("Block:variants")
        for element in variants_block:
            var = element.SelectField("name").GetStringData()
            self.variants.append(var)

class ManagedBlamModelOverride(ManagedBlam):
    """Overrides tag references in a .model tag"""
    def __init__(self, render_model, collision_model, physics_model, model_animation_graph):
        super().__init__()
        self.render_model = render_model
        self.collision_model = collision_model
        self.physics_model = physics_model
        self.model_animation_graph = model_animation_graph
        self.path = os.path.join(self.asset_dir, self.asset_name + ".model")
        self.tag_helper()

    def tag_edit(self, tag):
        if self.render_model and self.tag_exists(self.render_model):
            render_ref_override = self.TagPath_from_string(self.render_model)
            self.field_set_value_by_name(tag, "Reference:render model", render_ref_override)

        if self.collision_model and self.tag_exists(self.collision_model):
            collision_ref_override = self.TagPath_from_string(self.collision_model)
            self.field_set_value_by_name(tag, "Reference:collision model", collision_ref_override)

        if self.model_animation_graph and self.tag_exists(self.model_animation_graph):
            animation_ref_override = self.TagPath_from_string(self.model_animation_graph)
            self.field_set_value_by_name(tag, "Reference:animation", animation_ref_override)

        if self.physics_model and self.tag_exists(self.physics_model):
            physics_ref_override = self.TagPath_from_string(self.physics_model)
            self.field_set_value_by_name(tag, "Reference:physics_model", physics_ref_override)

class ManagedBlamSetStructureMetaRef(ManagedBlam):
    """Sets the reference to the given structure meta tag for the asset render model"""
    def __init__(self, structure_meta):
        super().__init__()
        self.structure_meta = structure_meta
        self.path = os.path.join(self.asset_dir, self.asset_name + ".render_model")
        self.tag_helper()

    def tag_edit(self, tag):
        if self.structure_meta and self.tag_exists(self.structure_meta):
            structure_meta_ref = self.TagPath_from_string(self.structure_meta)
            self.field_set_value_by_name(tag, "Reference:structure meta data", structure_meta_ref)

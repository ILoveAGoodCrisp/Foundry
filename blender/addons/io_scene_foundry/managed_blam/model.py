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

from io_scene_foundry.managed_blam import Tag

class ModelTag(Tag):
    tag_ext = 'model'
    
    def _read_fields(self):
        self.reference_render_model = self.tag.SelectField("Reference:render model")
        self.reference_collision_model = self.tag.SelectField("Reference:collision model")
        self.reference_animation = self.tag.SelectField("Reference:animation")
        self.reference_physics_model = self.tag.SelectField("Reference:physics_model")
        self.block_variants = self.tag.SelectField("Block:variants")
        
    def set_model_overrides(self, render_model, collision_model, model_animation_graph, physics_model):
        if render_model and self._tag_exists(render_model):
            self.reference_render_model.Path = self._TagPath_from_string(render_model)
            self.tag_has_changes = True
        if collision_model and self._tag_exists(collision_model):
            self.reference_collision_model.Path = self._TagPath_from_string(collision_model)
            self.tag_has_changes = True
        if model_animation_graph and self._tag_exists(model_animation_graph):
            self.reference_animation.Path = self._TagPath_from_string(model_animation_graph)
            self.tag_has_changes = True
        if physics_model and self._tag_exists(physics_model):
            self.reference_physics_model.Path = self._TagPath_from_string(physics_model)
            self.tag_has_changes = True
            
    def get_model_variants(self):
        return [v.SelectField("name").GetStringData() for v in self.block_variants.Elements]
        
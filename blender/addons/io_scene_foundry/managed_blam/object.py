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

from ..managed_blam import Tag

class ObjectTag(Tag):
    """For ManagedBlam task that cover all tags that are classed as objects"""
    def _read_fields(self):
        first_struct = self.tag.Fields[0]
        if first_struct.DisplayName == "object":
            object_struct = first_struct
        else:
            object_struct = first_struct.Elements[0].Fields[0]
        self.reference_model = self.tag.SelectField(f"{object_struct.FieldPath}/Reference:model")
            
    def get_model_tag_path(self):
        model_path = self.reference_model.Path
        if model_path:
            return model_path.RelativePathWithExtension
        else:
            print(f"{self.path} has no model reference")
            
    def set_model_tag_path(self, new_path: str):
        self.reference_model.Path = self._TagPath_from_string(new_path)
        self.tag_has_changes = True
        
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

from io_scene_foundry.managed_blam import Tag

class RenderModelTag(Tag):
    tag_ext = 'render_model'
    
    def _read_fields(self):
        self.reference_structure_meta_data = self.tag.SelectField("Reference:structure meta data") if self.corinth else None
        self.block_nodes = self.tag.SelectField("Block:nodes")
        self.struct_render_geometry = self.tag.SelectField("Struct:render geometry")
        
    def set_structure_meta_ref(self, meta_path):
        if self._tag_exists(meta_path):
            self.reference_structure_meta_data.Path = self._TagPath_from_string(meta_path)
            self.tag_has_changes = True
        else:
            print("Failed to add structure meta reference. Structure meta tag does not exist")
            
    def get_nodes(self):
        return [e.SelectField('name').GetStringData() for e in self.block_nodes.Elements]
    
    def read_render_geometry(self):
        render_geo = self._GameRenderGeometry()
        mesh_info = render_geo.GetMeshInfo(self.struct_render_geometry)
        print("index_bytes", mesh_info.index_bytes)
        print("index_count", mesh_info.index_count)
        print("parts", mesh_info.parts)
        print("subparts", mesh_info.subparts)
        print("triangle_count", mesh_info.triangle_count)
        print("vertex_bytes", mesh_info.vertex_bytes)
        print("vertex_count", mesh_info.vertex_count)
        print("vertex_type", mesh_info.vertex_type)
        
    def read_render_model(self):
        data_block = self.struct_render_geometry.Elements[0].SelectField('per mesh temporary')
        render_model = self._GameRenderModel()
        node_indices = render_model.GetNodeIndiciesFromMesh(data_block, 0)
        node_weights = render_model.GetNodeWeightsFromMesh(data_block, 0)
        normals = render_model.GetNormalsFromMesh(data_block, 0)
        positions = render_model.GetPositionsFromMesh(data_block, 0)
        tex_coords = render_model.GetTexCoordsFromMesh(data_block, 0)
        print("\nnode_indices")
        print("#"*50 + '\n')
        print([i for i in node_indices])
        print("\nnode_weights")
        print("#"*50 + '\n')
        print([i for i in node_weights])
        print("\nnormals")
        print("#"*50 + '\n')
        print([i for i in normals])
        print("\npositions")
        print("#"*50 + '\n')
        print([i for i in positions])
        print("\ntex_coords")
        print("#"*50 + '\n')
        print([i for i in tex_coords])


from math import radians
from typing import cast
import bpy
import os
from mathutils import Matrix, Quaternion, Vector
import numpy as np

from ..constants import WU_SCALAR

from .Tags import TagFieldElement
from ..managed_blam import Tag
from .. import utils
        
def decode_triangle_strip(indices):
    tris = []
    for i in range(len(indices) - 2):
        a, b, c = indices[i], indices[i + 1], indices[i + 2]

        if a == b or b == c or a == c:
            continue

        if i % 2 == 0:
            tris.append((a, b, c))
        else:
            tris.append((b, a, c))
    return tris

def encode_triangle_strip(triangles):
    if not triangles:
        return []

    strips = []
    prev_last = None

    for tri in triangles:
        a, b, c = tri

        if not strips:
            strips.extend([a, b, c])
        else:
            if prev_last is not None:
                strips.extend([prev_last, a])
            strips.extend([a, b, c])
        prev_last = c

    return strips
    
class PolyArtTag(Tag):
    tag_ext = 'polyart_asset'
    
    def _read_fields(self):
        self.block_vertices = self.tag.SelectField('Block:vertices')
        self.block_indices = self.tag.SelectField('Block:indices')
        
    def from_blender(self):
        pass
    
    
    def to_blender(self, collection=None):
        verts = []
        alphas = []
        uvs = []
        
        for element in self.block_vertices.Elements:
            vert_int16 = np.array([element.Fields[0].Data, element.Fields[1].Data, element.Fields[2].Data], dtype=np.int16)
            vert_uint16 = vert_int16.view(np.uint16)
            verts.append(vert_uint16.view(np.float16) * WU_SCALAR)
            
            alpha_int16 = np.array([element.Fields[3].Data])
            alpha_uint16 = alpha_int16.view(np.uint16)
            alphas.append(alpha_uint16.view(np.float16)[0])
            
            uv_int16 = np.array([element.Fields[4].Data, element.Fields[5].Data], dtype=np.int16)
            uv_uint16 = uv_int16.view(np.uint16)
            uvs.append(uv_uint16.view(np.float16))
            
        indices = decode_triangle_strip([element.Fields[0].Data for element in self.block_indices.Elements])
            
        mesh = bpy.data.meshes.new(self.tag_path.ShortName)
        
        mesh.from_pydata(vertices=verts, edges=[], faces=indices)
        
        uv_layer = mesh.uv_layers.new(name="UVMap0", do_init=False)
        for face in mesh.polygons:
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                uv_layer.data[loop_idx].uv = uvs[vert_idx]
                
        vcolor_attribute = mesh.color_attributes.new("Color", 'FLOAT_COLOR', 'POINT')
        rgba = np.repeat(np.array(alphas)[:, None], 4, axis=1)
        vcolor_attribute.data.foreach_set("color", rgba.ravel())
        
        mat = bpy.data.materials.get("polyart")
        if mat is None:
            mat = bpy.data.materials.new("polyart")
            mat.use_nodes = True
            tree = cast(bpy.types.NodeTree, mat.node_tree)
            tree.nodes.clear()
            node_attribute = tree.nodes.new(type="ShaderNodeAttribute")
            node_attribute.attribute_name = "Color"
            node_shader = tree.nodes.new(type='ShaderNodeBsdfPrincipled')
            tree.links.new(input=node_shader.inputs["Alpha"], output=node_attribute.outputs["Alpha"])
            node_output = tree.nodes.new(type='ShaderNodeOutputMaterial')
            tree.links.new(input=node_output.inputs[0], output=node_shader.outputs[0])
              
        mesh.materials.append(mat)
        
        ob = bpy.data.objects.new(mesh.name, mesh)
        
        if collection is None:
            bpy.context.scene.collection.objects.link(ob)
        else:
            collection.objects.link(ob)
            
        return ob


from math import radians
import bpy
import os
from mathutils import Matrix, Quaternion, Vector
import numpy as np

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
            verts.append(vert_uint16.view(np.float16))
            # alphas.append(to_float(element.Fields[3].Data))
            # uvs.append((to_float(element.Fields[4].Data), to_float(element.Fields[5].Data)))
            
        indices = decode_triangle_strip([element.Fields[0].Data for element in self.block_indices.Elements])
            
        mesh = bpy.data.meshes.new(self.tag_path.ShortName)
        mesh: bpy.types.Mesh
        ob = bpy.data.objects.new(mesh.name, mesh)
        
        mesh.from_pydata(vertices=verts, edges=[], faces=indices)
        
        if collection is None:
            bpy.context.scene.collection.objects.link(ob)
        else:
            collection.objects.link(ob)
            
        return ob
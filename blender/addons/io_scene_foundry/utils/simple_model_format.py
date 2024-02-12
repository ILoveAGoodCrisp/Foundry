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

import bpy
import bmesh
import struct

from mathutils import Vector

class SimpleModelFormat:
    """Model format that stores only vertex coordinates and face indices"""
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.packed_vertices = b''
        self.packed_faces = b''
        
    def from_mesh(self, mesh: bpy.types.Mesh):
        """Creates an smf object from the given mesh"""
        assert(isinstance(mesh, bpy.types.Mesh)), "mesh should be a bpy mesh"
        def to_bmesh(mesh: bpy.types.Mesh) -> bmesh.types.BMesh:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
            return bm
        
        bm = to_bmesh(mesh)
        
        vert_tuples = [vert.co.to_tuple() for vert in bm.verts]
        
        for t in vert_tuples:
            self.packed_vertices += struct.pack('3f', *t)
        
        for face in bm.faces:
            vert_indices = []
            for vert in face.verts:
                vert_indices.append(vert.index)
            
            self.packed_faces += struct.pack('I', len(vert_indices))
            for i in vert_indices:
                self.packed_faces += struct.pack('I', i)
            
        bm.free()
        
    def from_file(self, filepath):
        """Creates a new SimpleModelFormat representation from a .smf file"""
        assert(filepath.endswith(".smf")), "Filepath must end with .smf"
        with open(filepath, 'rb') as file:
            offset = struct.unpack('I', file.read(struct.calcsize('I')))[0]
            self.packed_vertices = file.read(offset)
            self.packed_faces = file.read()
            
        num_vertices = len(self.packed_vertices) // struct.calcsize('3f')
        for i in range(num_vertices):
            vertex = struct.unpack_from('3f', self.packed_vertices, i * struct.calcsize('3f'))
            self.vertices.append(Vector(vertex))
            
        offset = 0
        while offset < len(self.packed_faces):
            num_vertices = struct.unpack_from('I', self.packed_faces, offset)[0]
            offset += struct.calcsize('I')
            face = struct.unpack_from('{}I'.format(num_vertices), self.packed_faces, offset)
            self.faces.append(list(face))
            offset += num_vertices * struct.calcsize('I')
    
    def to_mesh(self, mesh_name='mesh') -> bpy.types.Mesh:
        """Creates a bpy mesh"""
        assert(self.vertices or self.faces), "No mesh data to read. Create this by calling from_file first"
        mesh = bpy.data.meshes.new(mesh_name)
        mesh.from_pydata(vertices=self.vertices, edges=[], faces=self.faces)
        
        return mesh
    
    def save_as(self, filepath: str):
        assert(filepath.endswith(".smf")), "Filepath must end with .smf"
        assert(type(self.packed_vertices) == bytes and type(self.packed_faces) == bytes), "packed vertices/faces data must be bytes. Use from_mesh before calling this"
        with open(filepath, mode='wb') as file:
            file.write(struct.pack('I', len(self.packed_vertices)))
            file.write(self.packed_vertices)
            file.write(self.packed_faces)
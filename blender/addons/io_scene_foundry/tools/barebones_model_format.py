import os
import bpy
import struct

from mathutils import Vector

class BarebonesModelFormat:
    """Model format that stores only vertex coordinates and face indices"""
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.packed_vertices = b''
        self.packed_faces = b''
        
    def from_mesh(self, mesh: bpy.types.Mesh):
        """Creates an bmf object from the given mesh"""
        assert(isinstance(mesh, bpy.types.Mesh)), "mesh should be a bpy mesh"
        
        vert_tuples = [vert.co.to_tuple() for vert in mesh.vertices]
        
        for t in vert_tuples:
            self.packed_vertices += struct.pack('3f', *t)
        
        for face in mesh.polygons:
            vert_indices = []
            for vert in face.vertices:
                vert_indices.append(vert.numerator)
            
            self.packed_faces += struct.pack('I', len(vert_indices))
            for i in vert_indices:
                self.packed_faces += struct.pack('I', i)
        
    def from_file(self, filepath):
        """Creates a new BarebonesModelFormat representation from a .bmf file"""
        assert(filepath.endswith(".bmf")), "Filepath must end with .bmf"
        assert(os.path.exists(filepath)), f"Path does not exist: {filepath}"
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
        assert(filepath.endswith(".bmf")), "Filepath must end with .bmf"
        assert(type(self.packed_vertices) == bytes and type(self.packed_faces) == bytes), "packed vertices/faces data must be bytes. Use from_mesh before calling this"
        with open(filepath, mode='wb') as file:
            file.write(struct.pack('I', len(self.packed_vertices)))
            file.write(self.packed_vertices)
            file.write(self.packed_faces)
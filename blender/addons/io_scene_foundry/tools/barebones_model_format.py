import os
from pathlib import Path
import bpy
import struct
from mathutils import Vector
import zlib
from ..constants import VALID_MESHES
from .. import utils

class NWO_OT_ExportBMF(bpy.types.Operator):
    bl_idname = "nwo.export_bmf"
    bl_label = "Export BMF"
    bl_description = "Exports a BMF, duh"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in VALID_MESHES

    def execute(self, context):
        ob: bpy.types.Object = context.object
        eval = ob.evaluated_get(context.evaluated_depsgraph_get())
        mesh = eval.to_mesh()
        bmf = BarebonesModelFormat()
        bmf.from_mesh(mesh)
        eval.to_mesh_clear()
        
        root = utils.addon_root()
        fp = Path(root, "resources", "scale_models", ob.name).with_suffix(".bmf")
        
        bmf.save_as(str(fp))
        self.report({'INFO'}, f"Saved to: {fp}")
        
        return {"FINISHED"}

class BarebonesModelFormat:
    def __init__(self):
        self.vertices = []
        self.faces = []

        self.packed = b''

        self.bmin = Vector((0, 0, 0))
        self.bmax = Vector((0, 0, 0))

    def from_mesh(self, mesh: bpy.types.Mesh):
        assert isinstance(mesh, bpy.types.Mesh), "mesh must be bpy.types.Mesh"

        mesh.calc_loop_triangles()

        verts = [v.co for v in mesh.vertices]

        self.bmin = Vector((
            min(v.x for v in verts),
            min(v.y for v in verts),
            min(v.z for v in verts),
        ))
        self.bmax = Vector((
            max(v.x for v in verts),
            max(v.y for v in verts),
            max(v.z for v in verts),
        ))

        size = self.bmax - self.bmin
        size.x = size.x or 1.0
        size.y = size.y or 1.0
        size.z = size.z or 1.0

        vert_bytes = bytearray()
        for v in verts:
            x = int((v.x - self.bmin.x) / size.x * 65535)
            y = int((v.y - self.bmin.y) / size.y * 65535)
            z = int((v.z - self.bmin.z) / size.z * 65535)
            vert_bytes.extend(struct.pack('3H', x, y, z))

        face_bytes = bytearray()
        for tri in mesh.loop_triangles:
            i0, i1, i2 = tri.vertices
            face_bytes.extend(struct.pack('3H', i0, i1, i2))

        header = struct.pack(
            'II6f',
            len(verts),
            len(mesh.loop_triangles),
            self.bmin.x, self.bmin.y, self.bmin.z,
            self.bmax.x, self.bmax.y, self.bmax.z,
        )

        raw = header + vert_bytes + face_bytes

        self.packed = zlib.compress(raw, level=9)

    def from_file(self, filepath):
        assert filepath.endswith(".bmf")
        assert os.path.exists(filepath)

        with open(filepath, 'rb') as f:
            self.packed = f.read()

        raw = zlib.decompress(self.packed)

        offset = 0

        num_verts, num_tris, *bbox = struct.unpack_from('II6f', raw, offset)
        offset += struct.calcsize('II6f')

        self.bmin = Vector(bbox[:3])
        self.bmax = Vector(bbox[3:])

        size = self.bmax - self.bmin
        size.x = size.x or 1.0
        size.y = size.y or 1.0
        size.z = size.z or 1.0

        self.vertices.clear()
        for _ in range(num_verts):
            x, y, z = struct.unpack_from('3H', raw, offset)
            offset += 6

            vx = self.bmin.x + (x / 65535) * size.x
            vy = self.bmin.y + (y / 65535) * size.y
            vz = self.bmin.z + (z / 65535) * size.z

            self.vertices.append(Vector((vx, vy, vz)))

        self.faces.clear()
        for _ in range(num_tris):
            i0, i1, i2 = struct.unpack_from('3H', raw, offset)
            offset += 6
            self.faces.append((i0, i1, i2))

    def to_mesh(self, name="mesh") -> bpy.types.Mesh:
        assert self.vertices and self.faces, "No data loaded"

        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(self.vertices, [], self.faces)
        return mesh
    
    def save_as(self, filepath):
        assert filepath.endswith(".bmf")
        assert isinstance(self.packed, (bytes, bytearray))

        with open(filepath, 'wb') as f:
            f.write(self.packed)
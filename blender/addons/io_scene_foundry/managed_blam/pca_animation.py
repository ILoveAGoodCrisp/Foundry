import numpy as np
import bpy
import struct
from typing import cast
from mathutils import Vector
from ..managed_blam import Tag

class PCAAnimationTag(Tag):
    tag_ext = "pca_animation"

    def _read_fields(self):
        self.block_mesh_data = self.tag.SelectField("Block:mesh data")
        self.block_frame_data = self.tag.SelectField("Block:frame data")

    def _raw_verts(self, mesh_data):
        block = mesh_data.SelectField("Block:raw blendshape verts")
        verts = [Vector((*e.Fields[0].Data,)) for e in block.Elements]
        return np.asarray([v[:] for v in verts], dtype=np.single)

    # ------------------------------------------------------------ #
    def import_animation(self,ob: bpy.types.Object, mesh_data_index: int, offset=0, count=1, shape_count= 16, shape_offset=0, percentile=100, fudge=0.75):
        mesh_data = self.block_mesh_data.Elements[mesh_data_index]
        vertices_per_shape = int(mesh_data.Fields[1].Data)

        vetices_array = self._raw_verts(mesh_data)
        all_shape_vertices = vetices_array.reshape(-1, vertices_per_shape, 3)
        shape_vertices = all_shape_vertices[shape_offset : shape_offset + shape_count]
        K = shape_vertices.shape[0]

        rows = []
        for elem in self.block_frame_data.Elements:
            buffer = bytes(elem.Fields[0].GetData())
            rows.append(struct.unpack('<'+'f'*(len(buffer)//4), buffer))

        row_length = len(rows)
        coefficient = np.zeros((row_length, K), np.float32)
        for i, r in enumerate(rows):
            coefficient[i, :min(K, len(r))] = r[:K]

        if count is None:
            count = row_length - offset
            
        coefficient = coefficient[offset:offset+count]

        span = np.percentile(np.abs(coefficient), percentile, axis=0) * fudge
        span[span < 1e-6] = 1.0

        me = cast(bpy.types.Mesh, ob.data)
        if not me.shape_keys:
            ob.shape_key_add(name="Basis", from_mix=False)

        basis = np.empty(len(me.vertices)*3, np.single)
        me.vertices.foreach_get("co", basis)
        basis = basis.reshape(-1, 3)
        scale = basis.ptp(0) / np.maximum(shape_vertices.reshape(-1,3).ptp(0), 1e-8)

        keys = []
        for k in range(K):
            kb = ob.shape_key_add(name=f"PC_{k+1}", from_mix=False)
            mesh_delta = shape_vertices[k] * scale * span[k]
            kb.data.foreach_set("co", (basis + mesh_delta).astype(np.single).ravel())
            kb.slider_min, kb.slider_max = -1.0, 1.0
            kb.value = 0.0
            keys.append(kb)

        for f, row in enumerate(coefficient, start=1):
            for k, kb in enumerate(keys):
                kb.value = float(row[k] / span[k])
                kb.keyframe_insert("value", frame=f)

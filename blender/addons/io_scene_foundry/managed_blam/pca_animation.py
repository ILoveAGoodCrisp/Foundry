

from collections import defaultdict
from enum import Enum
from math import radians
from pathlib import Path
from typing import cast
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
import numpy as np

from ..constants import WU_SCALAR
from ..managed_blam import Tag
import struct
        

class PCAAnimationTag(Tag):
    tag_ext = 'pca_animation'

    def _read_fields(self):
        self.block_mesh_data = self.tag.SelectField("Block:mesh data")
        self.block_frame_data = self.tag.SelectField("Block:frame data")
        
    def import_animation(self, ob: bpy.types.Object, mesh_data_index: int):
        mesh_data = self.block_mesh_data.Elements[mesh_data_index]
        vertices_per_shape = int(mesh_data.Fields[1].Data)

        # Step 1: Load blendshape vectors
        verts = self._get_blendshape_verts(mesh_data)  # shape: (num_components * num_verts, 3)
        components = verts.reshape(-1, vertices_per_shape, 3)  # shape: (num_components, num_verts, 3)

        # Step 2: Load per-frame coefficients
        coeffs_all = []
        for element in self.block_frame_data.Elements:
            coeff_bytes = bytes(element.Fields[0].GetData())
            coeffs = struct.unpack('<' + 'f' * (len(coeff_bytes) // 4), coeff_bytes)
            coeffs_all.append(coeffs)
        coeffs_all = np.array(coeffs_all, dtype=np.float32)

        num_components = components.shape[0]
        mesh = cast(bpy.types.Mesh, ob.data)

        if not mesh.shape_keys:
            ob.shape_key_add(name="Basis", from_mix=False)

        for frame_idx, coeffs in enumerate(coeffs_all):
            min_components = min(num_components, len(coeffs))
            shape = np.tensordot(coeffs[:min_components], components[:min_components], axes=(0, 0))

            # Transform to object space
            flat = np.array(shape, dtype=np.single).ravel()

            key = ob.shape_key_add(name=f"frame_{frame_idx}", from_mix=False)
            key.data.foreach_set("co", flat)


    def _get_blendshape_verts(self, mesh_data, matrix):
        block_verts = mesh_data.SelectField("Block:raw blendshape verts")
        verts = [Vector((*e.Fields[0].Data,)) * 100 for e in block_verts.Elements]
        return np.array([v.to_tuple() for v in verts], dtype=np.single)
        
        
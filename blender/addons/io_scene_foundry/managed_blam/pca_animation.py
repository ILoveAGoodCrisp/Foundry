import numpy as np
import bpy
import struct
from typing import cast
from mathutils import Vector

from .. import utils

from .render_model import RenderModelTag

from .connected_geometry import CompressionBounds
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
    
    def _decompress_verts(self, raw_verts: np.ndarray, bounds: CompressionBounds) -> np.ndarray:
        scale = np.array([bounds.x1 - bounds.x0, bounds.y1 - bounds.y0, bounds.z1 - bounds.z0])
        scale /= 10 # Maya scale
        scale *= utils.halo_scale(1)
        return raw_verts * scale

    # ------------------------------------------------------------ #
    def import_animation(self, ob: bpy.types.Object, mesh_data_index: int, bounds: CompressionBounds, offset, count, shape_count, shape_offset, name, blender_animation, group_name, kb_pca_min_max):
        print(f"--- Adding PCA animation for {name} to {ob.name}")
        mesh_data = self.block_mesh_data.Elements[mesh_data_index]
        vertices_per_shape = int(mesh_data.Fields[1].Data)

        compressed_vertices_array = self._raw_verts(mesh_data)
        vertices_array = self._decompress_verts(compressed_vertices_array, bounds)
        all_shape_vertices = vertices_array.reshape(-1, vertices_per_shape, 3)
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

        if not ob.data.shape_keys:
            keys = []
        else:
            keys = [kb for kb in ob.data.shape_keys.key_blocks if kb.name.startswith(group_name)]
            
        if not keys:
            me = cast(bpy.types.Mesh, ob.data)
            if not me.shape_keys:
                ob.shape_key_add(name="Basis", from_mix=False)

            basis = np.empty(len(me.vertices) * 3, np.single)
            me.vertices.foreach_get("co", basis)
            basis = basis.reshape(-1, 3)

            keys = []
            for k in range(K):
                kb = ob.shape_key_add(name=f"{group_name}_{k+1}", from_mix=False)
                mesh_delta = shape_vertices[k]
                kb.data.foreach_set("co", (basis + mesh_delta).astype(np.single).ravel())
                
                kb.slider_min, kb.slider_max = min(coefficient[:, k]), max(coefficient[:, k])
                
                kb_pca_min_max[kb] = kb.slider_min, kb.slider_max
                
                if kb.slider_min > 0:
                    kb.slider_min = 0
                    
                if kb.slider_max < 1:
                    kb.slider_max = 1
                
                kb.value = 0.0
                keys.append(kb)
            
        # New action
        action = bpy.data.actions.new(name=f"{name}_shape_keys")
        slot = action.slots.new('KEY', ob.data.name)
        track = blender_animation.action_tracks.add()
        track.is_shape_key_action = True
        track.object = ob
        track.action = action
        
        if not ob.data.shape_keys.animation_data:
            ob.data.shape_keys.animation_data_create()
        
        ob.data.shape_keys.animation_data.last_slot_identifier = slot.identifier
        ob.data.shape_keys.animation_data.action = action
        
        fcurves = utils.get_fcurves(action, slot)
        
        paths = {kb: f'key_blocks["{kb.name}"].value' for kb in keys}
        
        fc_map = {}
        for kb in keys:
            fcu = fcurves.new(data_path=paths[kb])
            fcu.keyframe_points.add(count=len(coefficient))
            fc_map[kb] = fcu

        for frame_idx, row in enumerate(coefficient, start=1):
            for k, kb in enumerate(keys):
                fcu = fc_map[kb]
                kp = fcu.keyframe_points[frame_idx - 1]
                value = float(row[k])
                pinned_value = utils.clamp(value, *kb_pca_min_max[kb])
                kp.co = (frame_idx, pinned_value)
                kp.interpolation = 'LINEAR'
                
    def to_blender(self, animations: dict, groups: dict):
        # Animations is a dict with keys of graph animation names and values of blender animations
        render_model_path = self.tag.SelectField("Reference:RenderModel").Path
        
        if not self.path_exists(render_model_path):
            return
        
        print("Importing PCA Animations")
        
        pca_mesh_vert_counts = {}
        pca_mesh_indices = []
        pca_objects = {}
        processed_groups = set()
        kb_pca_min_max = {}
        
        with RenderModelTag(path=render_model_path) as render_model:
            mesh_count = render_model.block_per_mesh_temporary.Elements.Count
            pca_mesh_indices = [element.Fields[0].Value for element in render_model.tag.SelectField("Struct:render geometry[0]/Block:PCA Mesh Indices").Elements if element.Fields[0].Value > -1 and element.Fields[0].Value < mesh_count]
            
            if not pca_mesh_indices:
                return
            
            for idx in pca_mesh_indices:
                mesh_element = render_model.block_per_mesh_temporary.Elements[idx]
                pca_mesh_vert_counts[mesh_element.Fields[0].Elements.Count] = idx
                
            compression_bounds = CompressionBounds(render_model.block_compression_info.Elements[0])
        
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                pca_index =  pca_mesh_vert_counts.get(len(ob.data.vertices))
                if pca_index is not None:
                    pca_objects[pca_index] = ob
        
        for name, blender_animation_name in animations.items():
            blender_animation = bpy.context.scene.nwo.animations.get(blender_animation_name)
            if blender_animation is None:
                continue
            for element in self.block_mesh_data.Elements:
                mesh_index = element.Fields[0].Data
                ob = pca_objects.get(mesh_index)
                if ob is None:
                    continue
                for anim_element in element.SelectField("Block:animations").Elements:
                    if anim_element.Fields[0].GetStringData() != name:
                        continue

                    offset = anim_element.Fields[1].Data
                    count = anim_element.Fields[2].Data
                    shape_offset = anim_element.Fields[3].Data
                    coefficient_count = anim_element.Fields[4].Data
                    
                    group_name = groups[shape_offset]

                    self.import_animation(ob, element.ElementIndex, compression_bounds, offset, count, coefficient_count, shape_offset, name, blender_animation, group_name, kb_pca_min_max)
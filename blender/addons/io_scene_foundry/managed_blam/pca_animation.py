import numpy as np
import bpy
from typing import cast

from .. import utils

from ..tags.pca import PCAAnimationDocument
from ..tags.blender import BlenderTag

class PCAAnimationTag(BlenderTag, PCAAnimationDocument):
    tag_ext = "pca_animation"

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)

    def _raw_verts(self, mesh_data):
        return np.asarray(self.raw_vertices(mesh_data), dtype=np.single).reshape(-1, 3)
    
    def _decompress_verts(self, raw_verts: np.ndarray, bounds) -> np.ndarray:
        scale = np.array([bounds.x1 - bounds.x0, bounds.y1 - bounds.y0, bounds.z1 - bounds.z0])
        scale /= 10 # Maya scale
        scale *= utils.halo_scale(1)
        return raw_verts * scale

    # ------------------------------------------------------------ #
    def import_animation(self, ob: bpy.types.Object, mesh_data_index: int, bounds, offset, count, shape_count, shape_offset, name, blender_animation, group_name, kb_pca_min_max):
        print(f"--- Adding PCA animation for {name} to {ob.name}")
        mesh_data = self.mesh_data()[mesh_data_index]
        vertices_per_shape = self.value(mesh_data, 'vertices per shape')
        if vertices_per_shape <= 0 or vertices_per_shape != len(ob.data.vertices):
            raise ValueError('PCA vertices per shape must match the target mesh')
        
        compressed_vertices_array = self._raw_verts(mesh_data)
        vertices_array = self._decompress_verts(compressed_vertices_array, bounds)
        all_shape_vertices = vertices_array.reshape(-1, vertices_per_shape, 3)
        shape_vertices = all_shape_vertices[shape_offset : shape_offset + shape_count]
        K = shape_vertices.shape[0]

        if shape_offset < 0 or shape_count <= 0 or K != shape_count:
            raise ValueError('PCA shape range is outside the available blendshapes')
        rows = self.coefficient_rows()

        row_length = len(rows)
        coefficient = np.zeros((row_length, K), np.float32)
        for i, r in enumerate(rows):
            coefficient[i, :min(K, len(r))] = r[:K]

        if count is None:
            count = row_length - offset
        if offset < 0 or count <= 0 or offset + count > row_length:
            raise ValueError('PCA frame range is outside the available coefficients')
            
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
                
        return ob.data.shape_keys, action, slot
                
    def to_blender(self, animations: dict, groups: dict, objects: list):
        # Animations is a dict with keys of graph animation names and values of blender animations
        shape_key_actions = {}
        
        render_info = self.render_mesh_info()
        if render_info is None:
            return
        
        pca_objects = {}
        kb_pca_min_max = {}
        
        pca_mesh_vert_counts, compression_bounds = render_info
        
        for ob in objects:
            pca_index = pca_mesh_vert_counts.get(len(ob.data.vertices))
            if pca_index is not None:
                pca_objects[pca_index] = ob
        
        for name, blender_animation_name in animations.items():
            blender_animation = self.scene_nwo.animations.get(blender_animation_name)
            if blender_animation is None:
                continue
            
            for element_index, element in enumerate(self.mesh_data()):
                mesh_index = self.value(element, 'render mesh index')
                ob = pca_objects.get(mesh_index)
                if ob is None:
                    continue
                for anim_element in self.block(element, 'animations'):
                    if self.value(anim_element, 'Name') != name:
                        continue

                    offset = self.value(anim_element, 'Offset')
                    count = self.value(anim_element, 'Count')
                    shape_offset = self.value(anim_element, 'PCA Shape Offset')
                    coefficient_count = self.value(anim_element, 'PCA coefficient Count')
                    
                    group_name = groups[shape_offset]

                    shape_key, action, slot = self.import_animation(ob, element_index, compression_bounds, offset, count, coefficient_count, shape_offset, name, blender_animation, group_name, kb_pca_min_max)
                    shape_key_actions[(action, slot)] = shape_key
                    
        return shape_key_actions

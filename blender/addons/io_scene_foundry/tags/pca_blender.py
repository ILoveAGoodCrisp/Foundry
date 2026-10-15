import numpy as np
import bpy
from typing import cast

from .. import import_transform, utils

from .pca import PCAAnimationDocument
from .blender import BlenderTag
from .pca_mapping import (SOURCE_TAG, prepare_mapping, source_mesh_index, store_mapping)

class PCAAnimationTag(BlenderTag, PCAAnimationDocument):
    tag_ext = "pca_animation"

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)

    def _raw_verts(self, mesh_data):
        return np.asarray(self.raw_vertices(mesh_data), dtype=np.single).reshape(-1, 3)
    
    def _decompress_verts(self, raw_verts: np.ndarray, bounds) -> np.ndarray:
        scale = np.array([bounds.x1 - bounds.x0, bounds.y1 - bounds.y0, bounds.z1 - bounds.z0])
        # Raw PCA positions are deltas in the render model's normalized bounds.
        # Bounds already include world-unit -> Halo-unit conversion, so apply
        # the same scene scale as the base mesh, without a positional offset.
        scale *= import_transform.scale_factor()
        return raw_verts * scale

    # ------------------------------------------------------------ #
    def import_animation(self, ob: bpy.types.Object, mesh_data_index: int, bounds, offset, count, shape_count, shape_offset, name, blender_animation, group_name):
        print(f"--- Adding PCA animation for {name} to {ob.name}")
        mesh_data = self.mesh_data()[mesh_data_index]
        vertices_per_shape = self.value(mesh_data, 'vertices per shape')
        if vertices_per_shape <= 0:
            raise ValueError('PCA vertices per shape must be positive')
        
        compressed_vertices_array = self._raw_verts(mesh_data)
        vertices_array = self._decompress_verts(compressed_vertices_array, bounds)
        all_shape_vertices = vertices_array.reshape(-1, vertices_per_shape, 3)
        shape_vertices = all_shape_vertices[shape_offset : shape_offset + shape_count]
        K = shape_vertices.shape[0]

        if shape_offset < 0 or shape_count <= 0 or K != shape_count:
            raise ValueError('PCA shape range is outside the available blendshapes')
        rows = self.coefficient_rows()

        row_length = len(rows)
        if count is None:
            count = row_length - offset
        if offset < 0 or count <= 0 or offset + count > row_length:
            raise ValueError('PCA frame range is outside the available coefficients')
            
        selected_rows = rows[offset:offset+count]
        if any(len(row) < K for row in selected_rows):
            raise ValueError('PCA frame has fewer coefficients than blendshapes')
        coefficient = np.asarray([row[:K] for row in selected_rows], dtype=np.float32)
        if not np.isfinite(coefficient).all():
            raise ValueError('PCA coefficients must be finite')

        cache = getattr(self, '_wrinkle_basis', None)
        if cache is None:
            cache = self._wrinkle_basis = {}
        if mesh_data_index not in cache:
            cache[mesh_data_index] = np.asarray(self.raw_tension(mesh_data), dtype=np.single).reshape(-1, vertices_per_shape, 3)
        tension = cache[mesh_data_index][shape_offset:shape_offset + K]
        valid_tension = tension.shape == shape_vertices.shape and np.isfinite(tension).all()
        mapping = prepare_mapping(ob.data, shape_vertices,
                                  tension if valid_tension else np.zeros_like(shape_vertices))
        shape_vertices = shape_vertices[:, mapping]
        if valid_tension:
            tension = tension[:, mapping]

        if not ob.data.shape_keys:
            keys = []
        else:
            keys = [ob.data.shape_keys.key_blocks.get(f'{group_name}_{k+1}') for k in range(K)]
            if any(key is None for key in keys):
                if any(key is not None for key in keys):
                    raise ValueError('PCA group has an incomplete set of shape keys')
                keys = []
            
        if not keys:
            me = cast(bpy.types.Mesh, ob.data)
            if not me.shape_keys:
                ob.shape_key_add(name="Basis", from_mix=False)

            basis = np.empty(len(me.vertices) * 3, np.single)
            me.shape_keys.reference_key.data.foreach_get("co", basis)
            basis = basis.reshape(-1, 3)

            keys = []
            for k in range(K):
                kb = ob.shape_key_add(name=f"{group_name}_{k+1}", from_mix=False)
                mesh_delta = shape_vertices[k]
                kb.data.foreach_set("co", (basis + mesh_delta).astype(np.single).ravel())
                
                kb.value = 0.0
                keys.append(kb)

        # Shared shapes must accommodate every clip, independent of import order.
        # Slider limits are UI/evaluation limits, never a reason to alter source keys.
        for k, kb in enumerate(keys):
            kb.slider_min = min(kb.slider_min, float(coefficient[:, k].min()), 0.0)
            kb.slider_max = max(kb.slider_max, float(coefficient[:, k].max()), 1.0)

        # Reconstruct authored wrinkle channels with these exact animated keys.
        # Keep all signed basis values; scale/offset belongs to packed buffers.
        from ..tools.wrinkle_tension import install_pca_tension, ensure_wrinkle_modifier
        if valid_tension:
            install_pca_tension(ob, keys, tension, shape_vertices)
        else:
            utils.print_warning(f'No usable authored wrinkle basis for {ob.name}; using geometry tension')
            ensure_wrinkle_modifier(ob)

        # New action
        action = bpy.data.actions.new(name=f"{name}_shape_keys")
        slot = action.slots.new('KEY', ob.data.name)
        track = blender_animation.action_tracks.add()
        track.is_shape_key_action = True
        track.object = ob
        track.action = action
        
        if not ob.data.shape_keys.animation_data:
            ob.data.shape_keys.animation_data_create()
        
        # The animation manager binds the action when its clip is selected.
        # Binding during import leaves an unrelated face animation running when
        # the selected skeletal clip (for example m10_plinth_start) has no PCA.
        
        fcurves = utils.get_fcurves(action, slot)
        
        paths = {kb: kb.path_from_id('value') for kb in keys}
        
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
                kp.co = (frame_idx, value)
                kp.interpolation = 'LINEAR'
                
        return ob.data.shape_keys, action, slot
                
    def to_blender(self, animations: dict, groups: dict, objects: list) -> dict:
        # Animations is a dict with keys of graph animation names and values of blender animations
        shape_key_actions = {}
        
        render_info = self.render_mesh_info()
        if render_info is None:
            utils.print_warning(f"Skipping PCA animations for {self.path}: "
                                "the render model is missing or has no matching PCA meshes")
            return shape_key_actions
        
        pca_objects = {}
        
        _, compression_bounds = render_info
        reference = self.reference(self.tag.root(), 'RenderModel').RelativePathWithExtension
        mesh_counts = {self.value(mesh, 'render mesh index'): self.value(mesh, 'vertices per shape')
                       for mesh in self.mesh_data()}
        
        for ob in objects:
            if ob.type != 'MESH':
                continue
            pca_index = source_mesh_index(ob.data, reference)
            if SOURCE_TAG not in ob.data:
                # Compatibility for older unmodified imports. New model imports
                # record their source identity before any editable cleanup.
                candidates = [index for index, count in mesh_counts.items() if count == len(ob.data.vertices)]
                if len(candidates) > 1:
                    raise ValueError(f'{ob.name}: ambiguous PCA mesh; reimport the model to record its source mapping')
                if candidates:
                    pca_index = candidates[0]
                    store_mapping(ob.data, reference, pca_index, mesh_counts[pca_index],
                                  range(len(ob.data.vertices)))
            if pca_index in mesh_counts:
                pca_objects.setdefault(pca_index, {}).setdefault(ob.data.as_pointer(), ob)
        
        for name, blender_animation_name in animations.items():
            blender_animation = self.scene_nwo.animations.get(blender_animation_name)
            if blender_animation is None:
                continue
            
            for element_index, element in enumerate(self.mesh_data()):
                mesh_index = self.value(element, 'render mesh index')
                targets = pca_objects.get(mesh_index)
                if not targets:
                    continue
                for anim_element in self.block(element, 'animations'):
                    if self.value(anim_element, 'Name') != name:
                        continue

                    offset = self.value(anim_element, 'Offset')
                    count = self.value(anim_element, 'Count')
                    shape_offset = self.value(anim_element, 'PCA Shape Offset')
                    coefficient_count = self.value(anim_element, 'PCA coefficient Count')
                    
                    group_name = groups[shape_offset]

                    for ob in targets.values():
                        shape_key, action, slot = self.import_animation(ob, element_index, compression_bounds, offset, count, coefficient_count, shape_offset, name, blender_animation, group_name)
                        shape_key_actions[(action, slot)] = shape_key
                    
        return shape_key_actions

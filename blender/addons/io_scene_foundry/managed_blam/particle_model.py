"""Import particle-model geometry through blam-tags."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

from ..tags.backend import TagDocument
from ..tags.blender import BlenderTag
from .. import import_transform


class ParticleModelTag(BlenderTag, TagDocument):
    tag_ext = 'particle_model'

    def _decoded_meshes(self, name):
        """Decode and validate every mesh before allocating Blender data."""
        records = self.tag.particle_meshes(Path(name).stem)
        decoded = []
        for mesh_index, record in enumerate(records):
            label = record.get('name') or f'{name}_{mesh_index + 1}'
            positions = [tuple(value) for value in record.get('positions', ())]
            normals = [tuple(value) for value in record.get('normals', ())]
            texcoords = [tuple(value) for value in record.get('texcoords', ())]
            flat_indices = list(record.get('indices', ()))

            if not positions:
                raise ValueError(f'{self.path}: particle mesh {label!r} has no vertices')
            if len(normals) != len(positions) or len(texcoords) != len(positions):
                raise ValueError(
                    f'{self.path}: particle mesh {label!r} has mismatched vertex streams')
            if any(len(value) != width for values, width in
                   ((positions, 3), (normals, 3), (texcoords, 2)) for value in values):
                raise ValueError(f'{self.path}: particle mesh {label!r} has malformed vertices')
            if any(not math.isfinite(component) for values in
                   (positions, normals, texcoords) for value in values for component in value):
                raise ValueError(f'{self.path}: particle mesh {label!r} has non-finite vertices')
            if not flat_indices or len(flat_indices) % 3:
                raise ValueError(f'{self.path}: particle mesh {label!r} has malformed triangles')
            if any(not isinstance(index, int) or isinstance(index, bool) or
                   not 0 <= index < len(positions) for index in flat_indices):
                raise ValueError(f'{self.path}: particle mesh {label!r} has an invalid vertex index')

            faces = [tuple(flat_indices[index:index + 3])
                     for index in range(0, len(flat_indices), 3)]
            decoded.append((label, positions, normals, texcoords, faces))
        if not decoded:
            raise ValueError(f'{self.path}: particle model has no reconstructable geometry')
        return decoded

    def to_blend_objects(self, collection: bpy.types.Collection, name: str) -> list[bpy.types.Object]:
        decoded = self._decoded_meshes(name)
        transform = import_transform.mesh_matrix()
        normal_transform = transform.to_3x3().inverted_safe().transposed()
        objects = []
        meshes = []
        try:
            for label, positions, normals, texcoords, faces in decoded:
                mesh = bpy.data.meshes.new(label)
                meshes.append(mesh)
                mesh.from_pydata([Vector(position) * 100 for position in positions], [], faces)
                mesh.transform(transform)

                uv_layer = mesh.uv_layers.new(name='UVMap0', do_init=False)
                for loop in mesh.loops:
                    u, v = texcoords[loop.vertex_index]
                    uv_layer.data[loop.index].uv = u, 1.0 - v

                transformed_normals = []
                for normal in normals:
                    value = normal_transform @ Vector(normal)
                    transformed_normals.append(
                        value.normalized() if value.length_squared else Vector((0, 0, 1)))
                mesh.normals_split_custom_set_from_vertices(transformed_normals)

                ob = bpy.data.objects.new(label, mesh)
                collection.objects.link(ob)
                objects.append(ob)
        except Exception:
            for ob in objects:
                bpy.data.objects.remove(ob, do_unlink=True)
            for mesh in meshes:
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            raise
        return objects

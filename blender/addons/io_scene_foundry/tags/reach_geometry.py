"""Reach-specific collision semantics; generic repairs live in bsp_import_geometry."""
import bpy
import numpy as np

from .. import face_attributes
from .. import utils


def preserve_two_sided_sealers(mesh):
    """Represent untextured two-sided collision without Tool's sealer type.

    Reach treats seam sealers as solid boundary faces even with a two-sided
    annotation. An ordinary collision-only face preserves the recovered sheet
    without making its free edges into holes in the surrounding solid shell.
    """
    two_sided = set()
    for prop in mesh.nwo.face_props:
        if prop.type == 'face_sides' and prop.two_sided:
            two_sided.update(i for i, value in enumerate(face_attributes.mask(mesh, prop)) if value)
    indices = [face.index for face in mesh.polygons if face.index in two_sided
               and face.material_index < len(mesh.materials)
               and mesh.materials[face.material_index] is not None
               and mesh.materials[face.material_index].name.lower().startswith('+seamsealer')
               and not mesh.materials[face.material_index].nwo.shader_path.strip()]
    if not indices:
        return 0
    material = next((m for m in bpy.data.materials if m.get('foundry_untextured_collision')), None)
    if material is None:
        material = bpy.data.materials.new('Reach two-sided collision')
        material['foundry_untextured_collision'] = True
    slot = next((i for i, m in enumerate(mesh.materials) if m == material), None)
    if slot is None:
        slot = len(mesh.materials)
        mesh.materials.append(material)
    mask = np.zeros(len(mesh.polygons), dtype=np.int8)
    for index in indices:
        mesh.polygons[index].material_index = slot
        mask[index] = 1
    utils.add_face_prop(mesh, 'face_mode', mask).face_mode = 'collision_only'
    utils.add_face_prop(mesh, 'global_material', mask).global_material = 'default'
    return len(indices)

# Compatibility imports for callers of the former Reach-only helpers.
from .bsp_import_geometry import (recover_mapped_collision, retriangulate_render_slivers,
                                  repair_collision_triangulation)

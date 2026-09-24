from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

from .connected_geometry import BSPSeam

from ..tools.property_apply import apply_props_material
from .blender import BlenderTag
from .seams import StructureSeamsDocument
from .. import import_transform
import os
from .. import utils

class StructureSeamsTag(BlenderTag, StructureSeamsDocument):
    tag_ext = 'structure_seams'

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)
    
    def to_blend_objects(self, seams: list, collection) -> list[bpy.types.Object]:
        print("Building Structure Seams")
        objects = []
        geometry = self.read_geometry()
        if len(seams) < len(geometry):
            raise ValueError('Scenario seam metadata does not cover every structure seam')
        for element in geometry:
            vertices = [[v * 100 for v in point] for point in element.vertices]
            
            if not vertices:
                utils.print_warning(f"Seam index {element.index} has no vertices")
                continue
            
            triangles = element.triangles
                
            if not triangles:
                utils.print_warning(f"Seam index {element.index} has no triangles")
                continue
            
            seam = seams[element.index]
            bsps = iter(seam.bsps)
            front_bsp = next(bsps, None)
            back_bsp = next(bsps, None)
            extra_bsp = next(bsps, None)
            if extra_bsp is not None:
                utils.print_warning(f"Found 3rd bsp for seam index {element.index}")
                utils.print_warning(seam.bsps)
                
            if front_bsp is None or back_bsp is None: continue
            
            mesh = bpy.data.meshes.new(f"seam")
            mesh.from_pydata(vertices=vertices, edges=[], faces=triangles)
            mesh.nwo.mesh_type = "_connected_geometry_mesh_type_seam"
            ob = bpy.data.objects.new(f"seam", mesh)
            
            apply_props_material(ob, "Seam")
            collection.objects.link(ob)
            objects.append(ob)
            
            ob.nwo.region_name = front_bsp
            ob.nwo.seam_back = back_bsp
            
            # Calculate correct normals direction
            closest_face = None
            min_distance = float('inf')
            bm = bmesh.new()
            bm.from_mesh(mesh)
            for face in bm.faces:
                face_center = face.calc_center_median()
                distance = (face_center - seam.origin).length
                if distance < min_distance:
                    min_distance = distance
                    closest_face = face
                    
            face_center = closest_face.calc_center_median()
            # utils.set_origin_to_point(ob, seam.origin)
            to_origin = (seam.origin - face_center).normalized()
            if closest_face.normal.dot(to_origin) < 0:
                bmesh.ops.reverse_faces(bm, faces=bm.faces)
                
            bm.to_mesh(mesh)
            bm.free()
            mesh.transform(import_transform.mesh_matrix())
            ob.matrix_world = import_transform.rotation_matrix()

        return objects

from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

from .connected_geometry import BSPSeam

from ..tools.property_apply import apply_props_material
from ..managed_blam import Tag
import os
from .. import utils

class StructureSeamsTag(Tag):
    tag_ext = 'structure_seams'
    
    def to_blend_objects(self, seams: list, collection) -> list[bpy.types.Object]:
        print("Building Structure Seams")
        objects = []
        seams_block = self.tag.SelectField("Block:seams")
        meshes = []
        for element in seams_block.Elements:
            vertices = []
            # for ve in element.SelectField("Struct:final[0]/Block:points").Elements:
            #     vertices.append([v * 100 for v in ve.Fields[0].Data])
            for ve in element.SelectField("Struct:original[0]/Block:original vertices").Elements:
                vertices.append([v * 100 for v in ve.Fields[0].Data])
            
            if not vertices:
                utils.print_warning(f"Seam index {element.ElementIndex} has no vertices")
                meshes.append(None)
                continue
            
            triangles = []
            for tri_element in element.SelectField("Struct:final[0]/Block:triangles").Elements:
                a = tri_element.Fields[1].Value
                b = tri_element.Fields[2].Value
                c = tri_element.Fields[3].Value
                triangles.append((a, b, c))
                
            if not triangles:
                utils.print_warning(f"Seam index {element.ElementIndex} has no triangles")
                meshes.append(None)
                continue
            
            edges = []
            for edge_element in element.SelectField("Struct:final[0]/Block:edges").Elements:
                a = edge_element.Fields[0].Value
                b = edge_element.Fields[1].Value
                edges.append((a, b))
                
            if not edges:
                utils.print_warning(f"Seam index {element.ElementIndex} has no edges")
                meshes.append(None)
                continue
            
            seam = seams[element.ElementIndex]
            bsps = iter(seam.bsps)
            front_bsp = next(bsps, None)
            back_bsp = next(bsps, None)
            extra_bsp = next(bsps, None)
            if extra_bsp is not None:
                utils.print_warning(f"Found 3rd bsp for seam index {element.ElementIndex}")
                utils.print_warning(seam.bsps)
                
            if front_bsp is None or back_bsp is None: continue
            
            mesh = bpy.data.meshes.new(f"seam")
            mesh.from_pydata(vertices=vertices, edges=[], faces=triangles)
            mesh.nwo.mesh_type = "_connected_geometry_mesh_type_seam"
            meshes.append(mesh)
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
            
        return objects
            
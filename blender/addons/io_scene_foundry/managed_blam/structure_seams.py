from pathlib import Path

import bpy

from ..tools.property_apply import apply_props_material
from ..managed_blam import Tag
import os
from .. import utils

class StructureSeamsTag(Tag):
    tag_ext = 'structure_seams'
    
    def to_blend_objects(self, seam_map: dict, collection: bpy.types.Collection) -> list[bpy.types.Object]:
        print("Building Structure Seams")
        objects = []
        seams_block = self.tag.SelectField("Block:seams")
        for element in seams_block.Elements:
            seam_id = element.SelectField("Struct:identifier[0]/seam_id0").Data
            bsp_name = seam_map.get(seam_id, None)
            if bsp_name is None:
                utils.print_warning(f"Failed to find seam in mapping with id {seam_id}")
                continue
            
            vertices = []
            for ve in element.SelectField("Struct:final[0]/Block:points").Elements:
                vertices.append([v * 100 for v in ve.Fields[0].Data])
            
            if not vertices:
                utils.print_warning(f"Seam index {element.ElementIndex} has no vertices")
                continue
            
            triangles = []
            for tri_element in element.SelectField("Struct:final[0]/Block:triangles").Elements:
                a = tri_element.Fields[1].Value
                b = tri_element.Fields[2].Value
                c = tri_element.Fields[3].Value
                triangles.append((a, b, c))
                
            if not triangles:
                utils.print_warning(f"Seam index {element.ElementIndex} has no triangles")
                continue
            
            mesh = bpy.data.meshes.new(f"seam::{bsp_name}")
            mesh.from_pydata(vertices=vertices, edges=[], faces=triangles)
            ob = bpy.data.objects.new(mesh.name, mesh)
            ob.nwo.region_name = bsp_name
            ob.nwo.seam_back_manual = True
            mesh.nwo.mesh_type = "_connected_geometry_mesh_type_seam"
            apply_props_material(ob, "Seam")
            collection.objects.link(ob)
            objects.append(ob)
            
        return objects
            
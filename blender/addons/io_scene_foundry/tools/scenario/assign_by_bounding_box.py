

import bpy
from mathutils import Vector

class NWO_OT_AssignByBoundingBox(bpy.types.Operator):
    bl_idname = "nwo.bsp_assign_by_bounding_box"
    bl_label = "Assign to BSP By Bounding Box"
    bl_description = "Assigns objects to bsps by which bsp bounding boxes they fall within"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.asset_type == 'scenario' and len(context.scene.nwo.regions_table) > 1

    def execute(self, context):
        
        return {"FINISHED"}
    
    
    
def create_bsp_bounding_box(context: bpy.types.Context, bsp: str):
    """Finds all structure geometry for a bsp and creates a bounding box representation"""
    bsp_structure = [ob for ob in context.view_layer.objects if ob.type == 'MESH' and ob.nwo.mesh_type == "_connected_geometry_mesh_type_structure" and not ob.nwo.ignore_for_export]
    if not bsp_structure:
        return
    for ob in bsp_structure:
        ob_world = ob.matrix_world.copy()
        ob: bpy.types.Object
        bbox = ob.bound_box
        bbox_world = [ob_world @ Vector(points) for points in bbox]
        min_x = min(min_x, bbox_world, key=lambda x: x[0])[0]
        max_x = max(max_x, bbox_world, key=lambda x: x[0])[0]
        min_y = min(min_y, bbox_world, key=lambda x: x[1])[1]
        max_y = max(max_y, bbox_world, key=lambda x: x[1])[1]
        min_z = min(min_z, bbox_world, key=lambda x: x[2])[2]
        max_z = max(max_z, bbox_world, key=lambda x: x[2])[2]
        
    return min_x, max_x, min_y, max_y, min_z, max_z

def test_object_in_bounding_box(ob, bbox):
    """Checks if the origin of an object lies within the given bounding box"""

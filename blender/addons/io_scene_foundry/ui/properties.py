import bpy

class MESH_PT_FoundryMeshData(bpy.types.Panel):
    bl_label = "Foundry Mesh Data"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data" 
    bl_parent_id = "DATA_PT_customdata"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.object.data.nwo, "from_vert_normals")
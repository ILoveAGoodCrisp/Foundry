import bpy

from io_scene_foundry.utils.nwo_utils import dot_partition

class NWO_StompMaterials(bpy.types.Operator):
    bl_idname = "nwo.stomp_materials"
    bl_label = "Clear Duplicate Materials"
    bl_description = "Clears duplicate materials from the scene, assigning the original material to material slots"
    bl_options = {"REGISTER", 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bpy.data.materials

    def execute(self, context):
        materials = bpy.data.materials
        # Collect base names
        basenames = set()
        for mat in materials:
            base = dot_partition(mat.name)
            if materials.get(base, 0):
                basenames.add(base)
            else:
                basenames.add(mat.name)
        # Get a list of duplicate materials
        dupemats = [mat for mat in materials if mat.name not in basenames]
        # Get a dict of base materials and a list of their duplicates
        dupe_base_dict = {}
        for dupe in dupemats:
            base_name = dot_partition(dupe.name)
            dupe_base_dict[dupe] = materials.get(base_name)
            
        # Loop all objects and replace duplicate materials
        for ob in bpy.data.objects:
            for slot in ob.material_slots:
                if slot.material in dupemats:
                    slot.material = dupe_base_dict[slot.material]
        
        dupe_count = len(dupemats)
        if dupe_count:
            # Clear duplicate materials from scene
            [materials.remove(mat) for mat in dupemats]
            self.report({'INFO'}, f"Stomped {dupe_count} duplicate materials")
        else:
            self.report({'INFO'}, "No duplicate materials found")
        return {"FINISHED"}


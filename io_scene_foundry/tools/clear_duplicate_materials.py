import os
import bpy

from io_scene_foundry.utils.nwo_utils import base_material_name, get_tags_path

class NWO_ClearShaderPaths(bpy.types.Operator):
    bl_idname = "nwo.clear_shader_paths"
    bl_label = "Clear Shader Paths"
    bl_description = "Clears Halo shader/material tag paths for all blender materials"
    bl_options = {"REGISTER", "UNDO"}
    
    cull_only_bad_paths: bpy.props.BoolProperty(
        name="Only Cull Bad Tag References",
        description="Only removes a shader path from a material if the shader path does not point to an existing tag",
    )

    @classmethod
    def poll(cls, context):
        return bpy.data.materials
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'cull_only_bad_paths')
        
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        tags_dir = get_tags_path()
        count = 0
        for mat in bpy.data.materials:
            if mat.nwo.shader_path:
                if self.cull_only_bad_paths and os.path.exists(tags_dir + mat.nwo.shader_path): continue
                mat.nwo.shader_path = ''
                count += 1
                
        self.report({'INFO'}, f'Removed {count} tag path{"s" if count != 1 else ""}')
        return {"FINISHED"}


class NWO_StompMaterials(bpy.types.Operator):
    bl_idname = "nwo.stomp_materials"
    bl_label = "Clear Duplicate Materials"
    bl_description = "Clears duplicate materials from the scene, assigning the original material to material slots. Duplicate materials are"
    bl_options = {"REGISTER", 'UNDO'}
    
    strip_legacy_halo_naming: bpy.props.BoolProperty(
        name="Strip Legacy Halo Shader prefixes/suffixes",
        description="Strips legacy Halo shader prefixes and suffixes from material names",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return bpy.data.materials
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'strip_legacy_halo_naming')
        
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        materials = bpy.data.materials
        # Collect base names
        basenames = set()
        for mat in materials:
            base = base_material_name(mat.name, self.strip_legacy_halo_naming)
            if materials.get(base, 0):
                basenames.add(base)
            else:
                basenames.add(mat.name)
        # Get a list of duplicate materials
        dupemats = [mat for mat in materials if mat.name not in basenames]
        # Get a dict of base materials and a list of their duplicates
        dupe_base_dict = {}
        for dupe in dupemats:
            base_name = base_material_name(mat.name, self.strip_legacy_halo_naming)
            dupe_base_dict[dupe] = materials.get(base_name)
            
        # Loop all objects and replace duplicate materials
        for ob in bpy.data.objects:
            for slot in ob.material_slots:
                if slot.material in dupemats:
                    slot.material = dupe_base_dict[slot.material]
                    
        # Ensure all material names equal their basenames
        for mat in materials:
            mat.name = base_material_name(mat.name, self.strip_legacy_halo_naming)
        
        dupe_count = len(dupemats)
        if dupe_count:
            # Clear duplicate materials from scene
            [materials.remove(mat) for mat in dupemats]
            self.report({'INFO'}, f"Stomped {dupe_count} duplicate materials")
        else:
            self.report({'INFO'}, "No duplicate materials found")
        return {"FINISHED"}


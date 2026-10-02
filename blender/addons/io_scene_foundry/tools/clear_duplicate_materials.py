from pathlib import Path
import bpy

from ..utils import base_material_name, get_tags_path

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
                if self.cull_only_bad_paths and Path(tags_dir, mat.nwo.shader_path).exists(): continue
                mat.nwo.shader_path = ''
                count += 1
                
        self.report({'INFO'}, f'Removed {count} tag path{"s" if count != 1 else ""}')
        return {"FINISHED"}


class NWO_StompMaterials(bpy.types.Operator):
    bl_idname = "nwo.stomp_materials"
    bl_label = "Clear Duplicate Materials"
    bl_description = "Clears duplicate materials from the scene, assigning the original material to material slots."
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
        starting_materials_count = len(bpy.data.materials)
        clear_duplicate_materials(self.strip_legacy_halo_naming)
        ending_materials_count = len(bpy.data.materials)
        if ending_materials_count < starting_materials_count:
            # Clear duplicate materials from scene
            self.report({'INFO'}, f"Stomped {starting_materials_count - ending_materials_count} duplicate materials")
        else:
            self.report({'INFO'}, "No duplicate materials found")
        return {"FINISHED"}

def clear_duplicate_materials(strip_legacy_halo_naming: bool, materials_scope=None):
    materials = bpy.data.materials
    # A shared basename does not imply a shared shader (for example Warthog
    # tire blur and chaingun blur). Keep the tag path in the material identity.
    canonical = {}
    replacements = {}
    to_remove = set()
    for mat in sorted(materials, key=lambda mat: mat.name != base_material_name(mat.name, strip_legacy_halo_naming)):
        base = base_material_name(mat.name, strip_legacy_halo_naming)
        path = mat.nwo.shader_path.replace('/', '\\').casefold()
        key = (base, path)
        original = canonical.setdefault(key, mat)
        if materials_scope is None or mat in materials_scope:
            if original != mat:
                replacements[mat] = original
                to_remove.add(mat)
                if materials_scope is not None and original not in materials_scope:
                    materials_scope.append(original)
            elif base != mat.name and not materials.get(base):
                mat.name = base
        
    # Loop all objects and replace duplicate materials
    for ob in bpy.data.objects:
        for slot in ob.material_slots:
            if slot.material in replacements:
                slot.material = replacements[slot.material]
    
    [materials.remove(mat) for mat in to_remove]
    if materials_scope is None:
        return [mat for mat in bpy.data.materials]
    else:
        return [mat for mat in bpy.data.materials if mat in materials_scope]

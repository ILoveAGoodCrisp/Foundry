import os
import bpy
from ..utils import (
    base_material_name,
    dot_partition,
    get_tags_path,
    has_shader_path,
    is_corinth,
    relative_path,
    shader_exts,
)

class NWO_ShaderFinder_Find(bpy.types.Operator):
    bl_idname = "nwo.shader_finder"
    bl_label = "Shader Finder"
    bl_description = 'Searches the tags folder (or the specified sub-directory) for shader/material tags and applies all that match blender material names'
    bl_options = {"REGISTER", "UNDO"}
    
    shaders_dir: bpy.props.StringProperty(
        name="Shaders Directory",
        description="Leave blank to search the entire tags folder for shaders or input a directory path to specify the folder (and sub-folders) to search for shaders. May be a full system path or tag relative path",
        default="",
    )
    overwrite_existing: bpy.props.BoolProperty(
        name="Overwrite Shader Paths",
        options=set(),
        description="Overwrite material/shader tag paths even if they're not empty",
        default=False,
    )
    
    def invoke(self, context: bpy.types.Context, _):
        return context.window_manager.invoke_props_dialog(self, width=600)

    def execute(self, context):
        return find_shaders(
            bpy.data.materials,
            self.report,
            self.shaders_dir,
            self.overwrite_existing,
        )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if is_corinth():
            return "Searches the tags folder for Materials (or only the specified directory) and applies all that match blender material names"
        else:
            return "Searches the tags folder for Shaders (or only the specified directory) and applies all that match blender material names"
        
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "shaders_dir", text="Limit Search to Directory (Optional)", icon='FILE_FOLDER')
        layout.prop(
            self,
            "overwrite_existing",
            text="Overwrite Existing Paths",
        )

class NWO_ShaderFinder_FindSingle(NWO_ShaderFinder_Find):
    bl_idname = "nwo.shader_finder_single"
    bl_description = 'Finds the first shader/material tag'
    
    def invoke(self, context: bpy.types.Context, _):
        return self.execute(context)

    def execute(self, context):
        scene = context.scene
        return find_shaders(
            [context.object.active_material],
            self.report,
            overwrite=True,
        )
    
    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if is_corinth():
            return "Returns the path of the first Material tag which matches the name of the active Blender material"
        else:
            return "Returns the path of the first Shader tag which matches the name of the active Blender material"


def scan_tree(shaders_dir, shaders):
    for root, dirs, files in os.walk(shaders_dir):
        for file in files:
            if file.endswith(shader_exts):
                shaders.add(os.path.join(root, file))

    return shaders


def find_shaders(materials_all, report=None, shaders_dir="", overwrite=False):
    materials = [mat for mat in materials_all if has_shader_path(mat)]
    shaders = set()
    update_count = 0
    no_path_materials = []
    tags_path = get_tags_path()

    if not shaders_dir:
        # clean shaders directory path
        shaders_dir = shaders_dir.replace('"', "").strip("\\")
        shaders_dir = relative_path(shaders_dir)

    # verify that the path created actually exists
    shaders_dir = os.path.join(tags_path, shaders_dir)
    shaders = set()
    if os.path.isdir(shaders_dir):
        scan_tree(shaders_dir, shaders)
        # loop through mats, find a matching shader, and apply it if the shader path field is empty
        for mat in materials:
            no_path = not bool(mat.nwo.shader_path)
            if no_path or overwrite:
                shader_path = find_shader_match(mat, shaders)
                if shader_path:
                    mat.nwo.shader_path = shader_path
                    update_count += 1
                elif no_path:
                    no_path_materials.append(mat.name)

    if report is not None:
        if no_path_materials:
            report({"WARNING"}, "Missing material paths:")
            for m in no_path_materials:
                report({"ERROR"}, m)
            if is_corinth():
                report(
                    {"WARNING"},
                    "These materials should either be given paths to Halo material tags, or specified as a Blender only material (by using the checkbox in Halo Material Paths)",
                )
            else:
                report(
                    {"WARNING"},
                    "These materials should either be given paths to Halo shader tags, or specified as a Blender only material (by using the checkbox in Halo Shader Paths)",
                )
            if update_count:
                report(
                    {"WARNING"},
                    f"Updated {update_count} material paths, but couldn't find paths for {len(no_path_materials)} materials. Click here for details",
                )
            else:
                report(
                    {"WARNING"},
                    f"Couldn't find paths for {len(no_path_materials)} materials. Click here for details",
                )
        elif no_path_materials:
            report(
                {"INFO"},
                f"Updated {update_count} material paths, and disabled export property for {len(no_path_materials)} materials",
            )
                
        else:
            report({"INFO"}, f"Updated {update_count} material paths")

        return {"FINISHED"}

    return no_path_materials


def find_shader_match(mat, shaders):
    """Tries to find a shader match. Includes logic for filtering out legacy material name prefixes/suffixes"""
    name_lower = mat.name.lower()
    material_name = base_material_name(name_lower, True)
    parts = material_name.split()
    material_name_ignore_first_word = material_name
    if len(parts) > 1:
        material_name_ignore_first_word = ' '.join(parts[1:])
    for s in shaders:
        # get just the shader name
        shader_name = dot_partition(os.path.basename(s)).lower()
        # changing this to check 3 versions, to ensure the correct material is picked
        if shader_name in (name_lower, dot_partition(name_lower), material_name, material_name_ignore_first_word):
            return s

    return ""

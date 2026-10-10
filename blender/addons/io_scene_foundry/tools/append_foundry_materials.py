

import bpy

from .. import utils
from ..tools.materials import special_materials, find_standard_material

class NWO_AppendFoundryMaterials(bpy.types.Operator):
    bl_idname = "nwo.append_foundry_materials"
    bl_label = "Append Special Materials"
    bl_description = "Appends special materials relevant to the current project and asset type to the blend file. Special materials are denoted by their '+' prefix"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return utils.current_project_valid()

    def execute(self, context):
        game = 'h4' if utils.is_corinth(context) else 'reach'
        asset_type = utils.get_scene_props().asset_type
        count = add_special_materials(game, asset_type)
        
        if count == 0:
            self.report({'INFO'}, 'All relevant special materials already added to blend file')
        else:
            self.report({'INFO'}, f'Added {count} material{"s" if count > 1 else ""} to blend file')
        return {"FINISHED"}
    
def ensure_special_material(definition, *, name=None, exclude=()):
    """Ensure a Foundry special material uses the invisible preview."""
    name = name or definition.name
    mat = find_standard_material(name, exclude)
    if mat is not None:
        utils.material_add_visibility(mat)
        return mat
    mat = bpy.data.materials.new(name)
    mat['foundry_standard_material'] = name
    mat.use_fake_user = True
    mat.use_nodes = True
    mat.diffuse_color = definition.color
    bsdf = next(node for node in mat.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = definition.color
    bsdf.inputs['Alpha'].default_value = definition.color[3]
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'BLENDED'
    else:
        mat.blend_method = 'BLEND'
    utils.material_add_visibility(mat)
    return mat


def add_special_materials(game, asset_type):
    blender_materials = bpy.data.materials
    count = 0
    for m in special_materials:
        if game in m.games and asset_type in m.asset_types:
            existed = blender_materials.get(m.name) is not None
            ensure_special_material(m)
            count += int(not existed)
            
    return count

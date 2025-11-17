

import bpy

from .. import utils
from ..tools.materials import special_materials

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
        asset_type = context.scene.nwo.asset_type
        count = add_special_materials(game, asset_type)
        
        if count == 0:
            self.report({'INFO'}, 'All relevant special materials already added to blend file')
        else:
            self.report({'INFO'}, f'Added {count} material{"s" if count > 1 else ""} to blend file')
        return {"FINISHED"}
    
def add_special_materials(game, asset_type):
    blender_materials = bpy.data.materials
    count = 0
    for m in special_materials:
        if game in m.games and asset_type in m.asset_types and not blender_materials.get(m.name):
            mat = blender_materials.new(m.name)
            mat.use_fake_user = True
            mat.diffuse_color = m.color
            bsdf = mat.node_tree.nodes[0]
            bsdf.inputs[0].default_value = m.color
            bsdf.inputs[4].default_value = m.color[3]
            mat.blend_method = 'BLEND'
            count += 1
            
    return count
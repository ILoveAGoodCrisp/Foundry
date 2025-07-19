"""Classes for the Material sub-panel"""

from pathlib import Path
import bpy
from ... import utils
from ...constants import face_prop_type_items, face_prop_descriptions

class NWO_OT_MaterialOpenTag(bpy.types.Operator):
    bl_idname = "nwo.open_halo_material"
    bl_label = "Open in Foundation"
    bl_description = "Opens the active material's Halo Shader/Material in Foundation"

    def execute(self, context):
        tag_path = Path(utils.get_tags_path(), context.object.active_material.nwo.shader_path)
        if tag_path.exists():
            utils.run_ek_cmd(["foundation", "/dontloadlastopenedwindows", str(tag_path)], True)
        else:
            if utils.is_corinth(context):
                self.report({"ERROR_INVALID_INPUT"}, "Material tag does not exist")
            else:
                self.report({"ERROR_INVALID_INPUT"}, "Shader tag does not exist")

        return {"FINISHED"}
    
class NWO_OpenImageEditor(bpy.types.Operator):
    bl_label = "Open in Image Editor"
    bl_idname = "nwo.open_image_editor"
    bl_description = "Opens the current image in the image editor specified in Blender Preferences"

    @classmethod
    def poll(self, context):
        ob = context.object
        if not ob:
            return
        mat = ob.active_material
        if not mat:
            return
        image = mat.nwo.active_image
        if not image:
            return
        path = image.filepath
        if not path:
            return
        return Path(image.filepath_from_user()).exists()

    def execute(self, context):
        try:
            bpy.ops.image.external_edit(filepath=context.object.active_material.nwo.active_image.filepath_from_user())
        except:
            self.report({'ERROR'}, 'Image editor could not be launched, ensure that the path in User Preferences > File is valid, and Blender has rights to launch it')
            return {'CANCELLED'}
        return {'FINISHED'}
    
class NWO_DuplicateMaterial(bpy.types.Operator):
    bl_idname = 'nwo.duplicate_material'
    bl_label = 'Duplicate Material'
    bl_description = 'Duplicates the active material'
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object
    
    def execute(self, context):
        ob = context.object
        if ob.active_material:
            new_mat = ob.active_material.copy()
        else:
            new_mat = bpy.data.materials.new(name='Material')
        ob.active_material = new_mat
        return {'FINISHED'}
    
class NWO_UL_MaterialPropList(bpy.types.UIList):
    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        row = layout.row()
        row.scale_x = 0.22
        match item.type:
            case 'emissive':
                row.prop(item, "material_lighting_emissive_color", text="")
            case 'lightmap_additive_transparency':
                row.prop(item, "lightmap_additive_transparency", text="")
            case 'lightmap_translucency_tint_color':
                row.prop(item, "lightmap_translucency_tint_color", text="")
            case _:
                row.prop(item, "color", text="")
        
        row = layout.row()      
        row.label(text=item.name, icon_value=icon)
        
class NWO_MT_MaterialAttributeAddMenu(bpy.types.Menu):
    bl_label = "Add Material Property"
    bl_idname = "NWO_MT_MaterialAttributeAddMenu"

    def draw(self, context):
        layout = self.layout
        corinth = utils.is_corinth(context)
        asset_type = context.scene.nwo.asset_type
        
        for name, display_name, mask in sorted(face_prop_type_items, key=lambda x: x[1]):
            games, asset_types = mask.split(":")
            games = games.split(",")
            asset_types = asset_types.split(",")
            if asset_type != 'resource':
                if corinth and "corinth" not in games:
                    continue
                elif not corinth and "reach" not in games:
                    continue
                elif asset_type not in asset_types:
                    continue
                elif name == "region":
                    continue
                elif name == 'global_material' and asset_type != "model" and not corinth:
                    continue
            layout.operator("nwo.material_attribute_add", text=display_name).options = name
            
class NWO_OT_MaterialAttributeAdd(bpy.types.Operator):
    bl_idname = "nwo.material_attribute_add"
    bl_label = "Add Material Attribute"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Add a new material attribute"

    @classmethod
    def poll(cls, context):
        return context and context.object and context.object.active_material
    
    @classmethod
    def description(cls, context, properties):
        return face_prop_descriptions[properties.options]

    options: bpy.props.EnumProperty(
        items=face_prop_type_items,
    )

    def execute(self, context):
        ob = context.object
        nwo = ob.active_material.nwo
        
        item = nwo.material_props.add()
        nwo.material_props_active_index = len(nwo.material_props) - 1
        
        item.type = self.options

        # item.color = utils.random_color()

        if self.options == "region":
            region = context.scene.nwo.regions_table[0].name
            item.region = region
        elif self.options == "global_material":
            item.global_material = "default"
            
        context.area.tag_redraw()
        return {"FINISHED"}

class NWO_OT_MaterialAttributeDelete(bpy.types.Operator):
    bl_idname = "nwo.material_attribute_delete"
    bl_label = "Delete"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context and context.object and context.object.active_material and context.object.active_material.nwo.material_props

    def execute(self, context):
        ob = context.object
        nwo = ob.active_material.nwo
        
        nwo.material_props.remove(nwo.material_props_active_index)
        nwo.material_props_active_index = min(nwo.material_props_active_index, len(nwo.material_props) - 1)

        context.area.tag_redraw()
        return {"FINISHED"}

class NWO_OT_MaterialAttributeMove(bpy.types.Operator):
    bl_idname = "nwo.material_attribute_move"
    bl_label = "Move"
    bl_options = {'UNDO'}

    direction: bpy.props.EnumProperty(
        name="Direction",
        items=(("UP", "UP", "UP"), ("DOWN", "DOWN", "DOWN")),
        default="UP",
    )

    @classmethod
    def poll(cls, context):
        return context and context.object and context.object.active_material and len(context.object.active_material.nwo.material_props) > 1

    def execute(self, context):
        ob = context.object
        nwo = ob.active_material.nwo
        material_attributes = nwo.material_props
        active_index = nwo.material_props_active_index
        delta = {
            "DOWN": 1,
            "UP": -1,
        }[self.direction]

        to_index = (active_index + delta) % len(material_attributes)

        material_attributes.move(active_index, to_index)
        nwo.material_props_active_index = to_index

        return {"FINISHED"}
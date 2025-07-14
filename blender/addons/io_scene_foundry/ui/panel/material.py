"""Classes for the Material sub-panel"""

from pathlib import Path
import bpy
from ... import utils

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
    
def toggle_active(context, option, bool_var):
    nwo = context.object.active_material.nwo

    match option:
        # lightmap
        case "lightmap_additive_transparency":
            nwo.lightmap_additive_transparency_active = bool_var
        case "lightmap_resolution_scale":
            nwo.lightmap_resolution_scale_active = bool_var
        case "lightmap_type":
            nwo.lightmap_type_active = bool_var
        case "lightmap_analytical_bounce_modifier":
            nwo.lightmap_analytical_bounce_modifier_active = bool_var
        case "lightmap_general_bounce_modifier":
            nwo.lightmap_general_bounce_modifier_active = bool_var
        case "lightmap_translucency_tint_color":
            nwo.lightmap_translucency_tint_color_active = bool_var
        case "lightmap_lighting_from_both_sides":
            nwo.lightmap_lighting_from_both_sides_active = bool_var
        case "lightmap_ignore_default_resolution_scale":
            nwo.lightmap_ignore_default_resolution_scale_active = bool_var
        case "lightmap_transparency_override":
            nwo.lightmap_transparency_override_active = bool_var
        case "lightmap_analytical_bounce_modifier":
            nwo.lightmap_analytical_bounce_modifier_active = bool_var
        case "lightmap_general_bounce_modifier":
            nwo.lightmap_general_bounce_modifier_active = bool_var
        case "lightmap_chart_group":
            nwo.lightmap_chart_group_active = bool_var
        # material lighting
        case "emissive":
            nwo.emissive_active = bool_var

class NWO_OT_AddEmissiveProperty(bpy.types.Operator):
    bl_idname = "nwo.add_emissive_property"
    bl_label = "Add"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material

    options: bpy.props.EnumProperty(
        items=[
            ("emissive", "Emissive", ""),
        ]
    )

    def execute(self, context):
        toggle_active(context, self.options, True)
        context.area.tag_redraw()
        return {"FINISHED"}
    
class NWO_OT_AddLightmapProperty(NWO_OT_AddEmissiveProperty):
    bl_idname = "nwo.add_lightmap_property"
    bl_label = "Add"
    bl_description = "Add a Lightmap Property"

    options: bpy.props.EnumProperty(
        items=[
            ("lightmap_additive_transparency", "Transparency", ""),
            ("lightmap_resolution_scale", "Resolution Scale", ""),
            ("lightmap_type", "Lightmap Type", ""),
            (
                "lightmap_translucency_tint_color",
                "Translucency Tint Color",
                "",
            ),
            (
                "lightmap_lighting_from_both_sides",
                "Lighting from Both Sides",
                "",
            ),
            ('lightmap_ignore_default_resolution_scale', 'Ignore Default Resolution Scale', ''),
            ('lightmap_transparency_override', 'Disable Lightmap Transparency', ''),
            ('lightmap_analytical_bounce_modifier', 'Analytical Bounce Modifier', ''),
            ('lightmap_general_bounce_modifier', 'General Bounce Modifier', ''),
            ('lightmap_chart_group', 'Chart Group', ''),
        ]
    )

class NWO_OT_RemoveMaterialProperty(bpy.types.Operator):
    """Removes a mesh property"""

    bl_idname = "nwo.remove_material_property"
    bl_label = "Remove"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object

    options: bpy.props.EnumProperty(
        items=[
            ("lightmap_additive_transparency", "Transparency", ""),
            ("lightmap_resolution_scale", "Resolution Scale", ""),
            ("lightmap_type", "Lightmap Type", ""),
            ("lightmap_translucency_tint_color", "Translucency Tint Color", ""),
            ("lightmap_lighting_from_both_sides", "Lighting from Both Sides", ""),
            ('lightmap_ignore_default_resolution_scale', 'Ignore Default Resolution Scale', ''),
            ("lightmap_transparency_override", "Disable Lightmap Transparency", ""),
            ("lightmap_analytical_bounce_modifier", "Analytical Bounce Modifier", ""),
            ("lightmap_general_bounce_modifier", "General Bounce Modifier", ""),
            ("lightmap_chart_group", "Chart Group", ""),
            ("emissive", "Emissive", ""),
        ]
    )

    def execute(self, context):
        toggle_active(context, self.options, False)
        context.area.tag_redraw()
        return {"FINISHED"}
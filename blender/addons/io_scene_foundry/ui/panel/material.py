"""Classes for the Material sub-panel"""

from pathlib import Path
import bpy
from ... import utils
from ...constants import face_prop_type_items, face_prop_descriptions, face_mode_items
from ...tags.halo1_emissive import (asset_shader_folder, localize_shader_environment,
                                    shader_environment_path,
                                    write_material_emissive, read_material_emissive)


class NWO_OT_RebuildFoundryMeshPreviews(bpy.types.Operator):
    bl_idname = 'nwo.rebuild_foundry_mesh_previews'
    bl_label = 'Rebuild Foundry Mesh Previews'
    bl_description = 'Rebuild Foundry face and material previews for every mesh in the scene, including hidden meshes, skipping linked library data'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.scene is not None and context.mode in {'OBJECT', 'EDIT_MESH'}
                and not utils.get_scene_props().export_in_progress
                and any(ob.type == 'MESH' for ob in context.scene.objects))

    def execute(self, context):
        objects = [ob for ob in context.scene.objects if ob.type == 'MESH']
        scene_meshes = {ob.data for ob in objects}
        # Object-linked material slots can differ between users of one mesh.
        scene_materials = {slot.material for ob in objects for slot in ob.material_slots
                           if slot.material is not None}
        meshes = {mesh for mesh in scene_meshes if mesh.library is None}
        materials = {mat for mat in scene_materials if mat.library is None}
        game = utils.get_game(utils.get_scene_props().scene_project)
        was_edit_mode = context.mode == 'EDIT_MESH'
        if was_edit_mode:
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            for mesh in meshes:
                utils.update_foundry_mesh(mesh, game, arrange_nodes=False, update_materials=False)
            for mat in materials:
                previous_nodes = set(mat.node_tree.nodes) if mat.node_tree else set()
                utils.update_foundry_material(mat, game, arrange_nodes=False)
                if mat.node_tree and set(mat.node_tree.nodes) != previous_nodes:
                    utils.arrange(mat.node_tree)
        finally:
            if was_edit_mode:
                bpy.ops.object.mode_set(mode='EDIT')

        message = f'Rebuilt Foundry previews for {len(meshes)} meshes and {len(materials)} materials'
        linked_meshes = len(scene_meshes) - len(meshes)
        linked_materials = len(scene_materials) - len(materials)
        if linked_meshes or linked_materials:
            message += f'; skipped {linked_meshes} linked meshes and {linked_materials} linked materials'
        self.report({'INFO'}, message)
        return {'FINISHED'}


class NWO_OT_UpdateHaloMaterialEmissive(bpy.types.Operator):
    bl_idname = 'nwo.update_halo_material_emissive'
    bl_label = 'Update Shader Emission'
    bl_description = 'Write Blender material emission to its Halo 1 or Halo 2 shader tag and update the preview'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        material = context.object.active_material if context.object else None
        project = utils.get_project(utils.get_scene_props().scene_project)
        return bool(project and project.game in {'halo1', 'halo2'} and material and
                    any(item.type == 'emissive' for item in material.nwo.material_props))

    def execute(self, context):
        material = context.object.active_material
        prop = next(item for item in material.nwo.material_props if item.type == 'emissive')
        try:
            scene = utils.get_scene_props()
            project = utils.get_project(scene.scene_project)
            if project is None or project.game not in {'halo1', 'halo2'}:
                raise ValueError('Select a Halo 1 or Halo 2 project')
            if not scene.is_valid_asset:
                raise ValueError('Set up and save the asset before updating shader emission')
            source = shader_environment_path(
                utils.relative_path(material.nwo.shader_path), project.tags_directory, project.game)
            target, copied = source, False
            if project.game == 'halo2':
                folder = asset_shader_folder(
                    scene.sidecar_path, project.data_directory, project.tags_directory)
                target, copied = localize_shader_environment(
                    source, folder, project.tags_directory, project.game)
            tag_path = str(target.relative_to(Path(project.tags_directory).resolve()))
            changed = write_material_emissive(
                tag_path, project.tags_directory,
                prop.material_lighting_emissive_power,
                prop.material_lighting_emissive_color, project.game)
            # Set the path only after writing. Its update callback can import
            # the tag and replace the Blender emission with the saved values.
            if material.nwo.shader_path != tag_path:
                material.nwo.shader_path = tag_path
            utils.update_classic_emissive_material(material, project.game)
            message = 'Updated shader emission and preview' if changed else 'Updated emission preview; tag already matches'
            if copied:
                message += ' in an asset shader copy'
            self.report({'INFO'}, message)
            return {'FINISHED'}
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class NWO_OT_MaterialOpenTag(bpy.types.Operator):
    bl_idname = "nwo.open_halo_material"
    bl_label = "Open in Tag Editor"
    bl_description = "Opens the active material's Halo Shader/Material in the current project's tag editor"

    @classmethod
    def poll(cls, context):
        return (utils.poll_project(cls) and context.object and context.object.active_material
                and bool(context.object.active_material.nwo.shader_path.strip()))

    def execute(self, context):
        if not utils.require_project(self):
            return {'CANCELLED'}
        tag_path = Path(utils.get_tags_path(), context.object.active_material.nwo.shader_path)
        if tag_path.exists():
            from ...tools.halo_launcher import open_tag_in_editor
            if not open_tag_in_editor(tag_path, context, self.report):
                return {"CANCELLED"}
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
        scene_nwo = utils.get_scene_props()
        project = utils.get_project(scene_nwo.scene_project)
        game = project.game if project else 'reach'
        if game in {'halo4', 'halo2a'}:
            game = 'corinth'
        asset_type = scene_nwo.asset_type
        
        for name, display_name, mask, _ in sorted(face_prop_type_items, key=lambda x: x[1]):
            games, asset_types = mask.split(":")
            games = games.split(",")
            asset_types = asset_types.split(",")
            if asset_type != 'resource':
                if game not in games:
                    continue
                elif asset_type not in asset_types:
                    continue
                # elif name == "region":
                #     continue
                elif name == 'global_material' and asset_type != "model" and game != 'corinth':
                    continue
            layout.operator("nwo.material_attribute_add", text=display_name).options = name
        if game == 'halo1' and asset_type == 'scenario':
            layout.operator("nwo.material_attribute_add", text="Emissive").options = 'emissive'
            
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
        scene_nwo = utils.get_scene_props()
        
        item = nwo.material_props.add()
        nwo.material_props_active_index = len(nwo.material_props) - 1
        
        if self.options in face_mode_items:
            item.type = 'face_mode'
            item.face_mode = self.options
        else:
            item.type = self.options

        # item.color = utils.random_color()

        if self.options == "region":
            region = scene_nwo.regions_table[0].name
            item.region = region
        elif self.options == "global_material":
            item.global_material = "default"
        elif self.options == 'emissive':
            project = utils.get_project(scene_nwo.scene_project)
            if project and project.game in {'halo1', 'halo2'}:
                try:
                    power, color = read_material_emissive(
                        utils.relative_path(nwo.shader_path), project.tags_directory, project.game)
                    item.material_lighting_emissive_power = power
                    item.material_lighting_emissive_color = color
                except (OSError, ValueError):
                    pass  # A new material may not have a shader yet.
            
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

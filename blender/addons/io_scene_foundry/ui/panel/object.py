"""Classes for Object Panel UI"""

from collections import defaultdict
from pathlib import Path
from typing import cast
import bpy
import bmesh
from uuid import uuid4
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix
import numpy as np

from ...constants import VALID_MESHES, face_prop_type_items, face_prop_descriptions, face_mode_items

from ...icons import get_icon_id
from ... import utils

from ...managed_blam.globals import GlobalsTag
from ...managed_blam.model import ModelTag
from ...managed_blam.object import ObjectTag
from ...managed_blam.render_model import RenderModelTag

int_highlight = 0

# FRAME PROPS

class NWO_OT_SelectChildObjects(bpy.types.Operator):
    bl_idname = "nwo.select_child_objects"
    bl_label = "Select Child Objects"
    bl_description = "Selects the child objects of this frame"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object

    def execute(self, context):
        ob = context.object
        children = ob.children_recursive
        for child in children:
            child.select_set(True)
        self.report({'INFO'}, f"Selected {len(children)} child objects")
        return {"FINISHED"}

class NWO_OT_RemapChildDriversToArmature(bpy.types.Operator):
    bl_idname = "nwo.remap_child_drivers_to_armature"
    bl_label = "Remap Drivers"
    bl_description = "Remaps custom property drivers on this armature's direct children so any armature object driver targets point to the selected armature"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and ob.type == 'ARMATURE'

    @staticmethod
    def _id_prop_name_from_data_path(data_path: str) -> str | None:
        if not data_path.startswith('["'):
            return None

        prop_name, separator, _ = data_path[2:].partition('"]')
        if not separator:
            return None

        return prop_name

    @classmethod
    def _clone_id_prop_value(cls, value):
        if hasattr(value, "to_dict"):
            return {k: cls._clone_id_prop_value(v) for k, v in value.to_dict().items()}
        if hasattr(value, "items"):
            return {k: cls._clone_id_prop_value(v) for k, v in value.items()}
        if hasattr(value, "to_list"):
            return [cls._clone_id_prop_value(v) for v in value.to_list()]
        if isinstance(value, list):
            return [cls._clone_id_prop_value(v) for v in value]
        if isinstance(value, tuple):
            return [cls._clone_id_prop_value(v) for v in value]
        return value

    def _copy_missing_armature_prop(self, target_armature: bpy.types.Object, source_armature: bpy.types.Object, data_path: str) -> bool:
        prop_name = self._id_prop_name_from_data_path(data_path)
        if not prop_name or prop_name in target_armature.keys() or prop_name not in source_armature.keys():
            return False

        # Copy the source armature's current live value when we need to create
        # the property on the selected armature for a remapped driver.
        source_value = self._clone_id_prop_value(source_armature[prop_name])
        target_armature[prop_name] = source_value

        source_ui = source_armature.id_properties_ui(prop_name)
        target_ui = target_armature.id_properties_ui(prop_name)
        if hasattr(source_ui, "as_dict"):
            ui_data = {k: v for k, v in source_ui.as_dict().items() if v is not None}
            if ui_data:
                try:
                    target_ui.update(**ui_data)
                except TypeError:
                    supported_keys = {"description", "default", "min", "max", "soft_min", "soft_max", "subtype"}
                    target_ui.update(**{k: v for k, v in ui_data.items() if k in supported_keys})

        return True

    def execute(self, context):
        armature = context.object
        updated_children = 0
        updated_drivers = 0
        updated_targets = 0
        added_props = 0

        for child in armature.children:
            animation_data = child.animation_data
            if animation_data is None:
                continue

            child_updated = False
            for fcurve in animation_data.drivers:
                if not fcurve.data_path.startswith('["'):
                    continue

                driver_updated = False
                for variable in fcurve.driver.variables:
                    for target in variable.targets:
                        target_id = target.id
                        if not isinstance(target_id, bpy.types.Object):
                            continue
                        if target_id.type != 'ARMATURE' or target_id == armature:
                            continue

                        if self._copy_missing_armature_prop(armature, target_id, target.data_path):
                            added_props += 1

                        # Blender can otherwise leave the single-property target in
                        # an invalid state until the target ID gets a data refresh.
                        armature.update_tag(refresh={'DATA'})
                        target.id = armature
                        updated_targets += 1
                        driver_updated = True
                        child_updated = True

                if driver_updated:
                    updated_drivers += 1

            if child_updated:
                updated_children += 1

        if updated_targets:
            self.report({'INFO'}, f"Remapped {updated_targets} driver target{'' if updated_targets == 1 else 's'} across {updated_drivers} driver{'' if updated_drivers == 1 else 's'} on {updated_children} child object{'' if updated_children == 1 else 's'} and copied {added_props} missing armature propert{'y' if added_props == 1 else 'ies'}")
            return {"FINISHED"}

        self.report({'WARNING'}, "No child custom property drivers were found that target a different armature")
        return {"CANCELLED"}
    
# MARKER

class NWO_OT_SetHintName(bpy.types.Operator):
    bl_idname = "nwo.set_hint_name"
    bl_label = "Set Hint Name"
    bl_description = "Sets a valid hint marker name"
    bl_options = {'REGISTER', 'UNDO'}
    
    marker_hint_type: bpy.props.EnumProperty(
        name="Type",
        options=set(),
        description="",
        items=[
            ("bunker", "Bunker", ""),
            ("corner", "Corner", ""),
            ("vault", "Vault", ""),
            ("mount", "Mount", ""),
            ("hoist", "Hoist", ""),
        ],
    )
    
    marker_hint_side: bpy.props.EnumProperty(
        name="Side",
        options=set(),
        description="",
        items=[
            ("right", "Right", ""),
            ("left", "Left", ""),
        ],
    )

    marker_hint_height: bpy.props.EnumProperty(
        name="Height",
        options=set(),
        description="",
        items=[
            ("step", "Step", ""),
            ("crouch", "Crouch", ""),
            ("stand", "Stand", ""),
        ],
    )
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'EMPTY'
    
    def execute(self, context):
        ob = context.object
        name = "hint_"
        if self.marker_hint_type == "bunker":
            name += "bunker"
        elif self.marker_hint_type == "corner":
            name += "corner_"
            if self.marker_hint_side == "right":
                name += "right"
            else:
                name += "left"

        else:
            if self.marker_hint_type == "vault":
                name += "vault_"
            elif self.marker_hint_type == "mount":
                name += "mount_"
            else:
                name += "hoist_"

            if self.marker_hint_height == "step":
                name += "step"
            elif self.marker_hint_height == "crouch":
                name += "crouch"
            else:
                name += "stand"
        
        ob.name = name
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "marker_hint_type", expand=True)
        if self.marker_hint_type == "corner":
            row = layout.row(align=True)
            row.prop(self, "marker_hint_side", expand=True)
        elif self.marker_hint_type in (
            "vault",
            "mount",
            "hoist",
        ):
            row = layout.row(align=True)
            row.prop(self, "marker_hint_height", expand=True)

# FACE PROPERTIES #
class NWO_MT_FaceAttributeAddMenu(bpy.types.Menu):
    bl_label = "Add Face Property"
    bl_idname = "NWO_MT_FaceAttributeAddMenu"

    def draw(self, context):
        layout = self.layout
        scene_nwo = utils.get_scene_props()
        corinth = utils.is_corinth(context)
        asset_type = scene_nwo.asset_type
        
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
                # elif name == "region" and context.mode != 'EDIT_MESH':
                #     continue
                elif name not in {'global_material', 'slip_surface', 'ladder', 'face_sides'}  and asset_type == "model" and context.object.data.nwo.mesh_type == '_connected_geometry_mesh_type_collision':
                    continue
                elif name in {'global_material', 'slip_surface', 'ladder'} and asset_type == "model" and context.object.data.nwo.mesh_type != '_connected_geometry_mesh_type_collision':
                    continue
                elif name == 'global_material' and asset_type != "model" and not corinth:
                    continue
            layout.operator("nwo.face_attribute_add", text=display_name).options = name


class NWO_UL_FacePropList(bpy.types.UIList):
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
        is_mesh = context.object.type == 'MESH'
        face_count = len(data.id_data.polygons) if is_mesh else 0
        row = layout.row()
        row.scale_x = 0.24
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
        row = layout.row()
        row.alignment = "RIGHT"
        if not is_mesh or face_count == item.face_count:
            row.label(text="All")
        elif item.face_count:
            if item.face_count > face_count:
                row.label(text="Refresh Required")
            else:
                row.label(text=utils.human_number(item.face_count))
        else:
            row.label(text=f"Unassigned")
            
class NWO_OT_FaceAttributeConsolidate(bpy.types.Operator):
    bl_idname = "nwo.face_attribute_consolidate"
    bl_label = "Merge Face Attributes"
    bl_description = "Consolidates all face attributes into the minimum possible amount"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.data.nwo.face_props and context.mode != 'EDIT_MESH'
    
    def execute(self, context):
        utils.consolidate_face_attributes(context.object.data)
        return {"FINISHED"}
                
class NWO_OT_FaceAtributeCountRefresh(bpy.types.Operator):
    bl_idname = "nwo.face_attribute_count_refresh"
    bl_label = "Refresh Face Counts"
    bl_description = "Refreshes the face counts of all face property attributes in case they are out of sync"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.data.nwo.face_props

    def execute(self, context):
        mesh = context.object.data
        edit_mode = context.mode == "EDIT_MESH"
        
        for prop in mesh.nwo.face_props:
            if edit_mode:
                prop.face_count = utils.face_attribute_count_edit_mode(mesh, prop)
            else:
                prop.face_count = utils.face_attribute_count(mesh, prop)
            
        return {"FINISHED"}
    
class NWO_OT_ConsolidateFaceProps(bpy.types.Operator):
    bl_idname = "nwo.consolidate_face_props"
    bl_label = "Consolidate Face Properties"
    bl_description = "Merges any duplicate face properties together and removes redundant ones (like two-sided on sphere collision)"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and context.object.data.nwo.face_props
    
    def execute(self, context):
        utils.consolidate_face_attributes(context.object.data)
        return {"FINISHED"}

class NWO_OT_EditMode(bpy.types.Operator):
    """Toggles Edit Mode for face layer editing"""

    bl_idname = "nwo.edit_face_attributes"
    bl_label = "Enter Edit Mode"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == "MESH" and context.mode != 'EDIT_MESH' and bpy.ops.object.mode_set.poll()

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        return {"FINISHED"}
    
attributes_list = []
    
class NWO_OT_ChangeAttribute(bpy.types.Operator):
    bl_idname = "nwo.change_attribute"
    bl_label = "Change Mesh Attribute"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Lets you change the mesh attribute pointed to by this face property (and optionally rename it). Only single value (bool, integer, float) face attributes are supported. For Foundry, a face either has a property or it doesn't so while you can use integers or floats, they will just be true if they are a value other than 0"
    
    @classmethod
    def poll(self, context):
        return context.object and context.object.type in VALID_MESHES and context.object.data.nwo.face_props
    
    def new_attribute_items(self, context):
        global attributes_list
        return [(attr.name, attr.name, "") for attr in attributes_list]
        
    
    new_attribute: bpy.props.EnumProperty(
        name="New Attribute",
        description="The new attribute to associate with this face property. Available items come from mesh attributes and must be a single value (bool, integer, float) face attribute",
        items=new_attribute_items,
        options={'SKIP_SAVE'}
    )
    
    name_override: bpy.props.StringProperty(
        name="Name Override",
        description="Changes the name of the new attribute above. Leave blank for no change",
        options={'SKIP_SAVE'}
    )
    
    def execute(self, context):
        mesh = cast(bpy.types.Mesh, context.object.data)
        prop = mesh.nwo.face_props[mesh.nwo.face_props_active_index]
        attribute = mesh.attributes.get(self.new_attribute)
        if attribute is None:
            self.report({'WARNING'}, f"Failed to find attribute {self.new_attribute}")
            return {'CANCELLED'}
            
        if self.name_override.strip():
            attribute.name = self.name_override.strip()
            
        prop.attribute_name = attribute.name
        self.report({'INFO'}, f"Updated face property attribute to: {prop.attribute_name}")
        return {'FINISHED'}
            
    def invoke(self, context: bpy.types.Context, _):
        mesh = cast(bpy.types.Mesh, context.object.data)
        prop = mesh.nwo.face_props[mesh.nwo.face_props_active_index]
        current_attribute_name = prop.attribute_name
        current_attribute = mesh.attributes.get(current_attribute_name)
        global attributes_list
        if current_attribute is None:
            attributes_list = [attr for attr in mesh.attributes if attr.domain == 'FACE' and attr.data_type in {'FLOAT', 'INT', 'BOOLEAN'}]
        else:
            attributes_list = [current_attribute]
            attributes_list.extend([attr for attr in mesh.attributes if attr.domain == 'FACE' and attr.data_type in {'FLOAT', 'INT', 'BOOLEAN'} and attr != current_attribute])

        return context.window_manager.invoke_props_dialog(self, width=500)
        
    def draw(self, context):
        layout = cast(bpy.types.UILayout, self.layout)
        layout.use_property_split = True
        layout.prop(self, "new_attribute")
        layout.prop(self, "name_override")


class NWO_OT_FaceAttributeAdd(bpy.types.Operator):
    bl_idname = "nwo.face_attribute_add"
    bl_label = "Add Face Attribute"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Add a new face attribute"

    @classmethod
    def poll(cls, context):
        return context and context.object and context.object.type in VALID_MESHES
    
    @classmethod
    def description(cls, context, properties):
        return face_prop_descriptions[properties.options]

    options: bpy.props.EnumProperty(
        items=face_prop_type_items,
    )

    def execute(self, context):
        ob = context.object
        mesh = ob.data
        nwo = mesh.nwo
        scene_nwo = utils.get_scene_props()
        
        item = nwo.face_props.add()
        nwo.face_props_active_index = len(nwo.face_props) - 1
        
        if self.options in face_mode_items:
            item.type = 'face_mode'
            item.face_mode = self.options
        else:
            item.type = self.options
        
        if ob.type == 'MESH':
            if context.mode == 'EDIT_MESH':
                attribute, face_count = utils.assign_face_attribute_edit_mode(mesh)
                item.face_count = face_count
                item.attribute_name = attribute.name
            else:
                attribute, face_count = utils.assign_face_attribute(mesh)
                item.face_count = face_count
                item.attribute_name = attribute.name
        
            
        item.color = utils.random_color()
        if nwo.highlight:
            bpy.ops.nwo.face_attribute_color_all(enable_highlight=nwo.highlight)

        if self.options == "region":
            region = scene_nwo.regions_table[0].name
            item.region = region
        elif self.options == "global_material":
            item.global_material = "default"
            
        context.area.tag_redraw()
        return {"FINISHED"}

class NWO_OT_FaceAttributeDelete(bpy.types.Operator):
    bl_idname = "nwo.face_attribute_delete"
    bl_label = "Delete"
    bl_options = {"UNDO"}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type in VALID_MESHES and context.object.data.nwo.face_props

    def execute(self, context):
        ob = context.object
        mesh = ob.data
        nwo = mesh.nwo
        
        if ob.type == 'MESH':
            if context.mode == 'EDIT_MESH':
                utils.delete_face_attribute_edit_mode(mesh, nwo.face_props_active_index)
            else:
                utils.delete_face_attribute(mesh, nwo.face_props_active_index)
        else:
            mesh.nwo.face_props.remove(mesh.nwo.face_props_active_index)
            mesh.nwo.face_props_active_index = min(mesh.nwo.face_props_active_index, len(mesh.nwo.face_props) - 1)
        
        if nwo.highlight:
            bpy.ops.nwo.face_attribute_color_all(enable_highlight=nwo.highlight)

        context.area.tag_redraw()
        return {"FINISHED"}


class NWO_OT_FaceAttributeAssign(bpy.types.Operator):
    bl_idname = "nwo.face_attribute_assign"
    bl_label = "Assign"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(self, context):
        return context.object and context.object.type in VALID_MESHES and context.object.data.nwo.face_props and context.object.type == 'MESH'

    def execute(self, context):
        mesh = context.object.data
        nwo = mesh.nwo
        item = nwo.face_props[nwo.face_props_active_index]
        
        if context.mode == 'EDIT_MESH':
            attribute, face_count = utils.assign_face_attribute_edit_mode(mesh)
        else:
            attribute, face_count = utils.assign_face_attribute(mesh)
        
        item.attribute_name = attribute.name
        item.face_count = face_count
        
        if nwo.highlight and bpy.ops.nwo.face_attribute_color_all.poll():
            bpy.ops.nwo.face_attribute_color_all(enable_highlight=nwo.highlight)

        context.area.tag_redraw()
        return {"FINISHED"}
    
class NWO_OT_FaceAttributeRemove(bpy.types.Operator):
    bl_idname = "nwo.face_attribute_remove"
    bl_label = "Remove"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(self, context):
        return context.object and context.object.type in VALID_MESHES and context.object.data.nwo.face_props and context.mode == 'EDIT_MESH'

    def execute(self, context):
        mesh = context.object.data
        nwo = mesh.nwo
        item = nwo.face_props[nwo.face_props_active_index]
        
        attribute, face_count = utils.remove_face_attribute_edit_mode(mesh)
        
        item.attribute_name = attribute.name
        item.face_count = face_count

        context.area.tag_redraw()

        return {"FINISHED"}

class NWO_OT_FaceAttributeSetAll(bpy.types.Operator):
    bl_idname = "nwo.face_attribute_set_all"
    bl_label = "Set All"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(self, context):
        return context.object and context.object.type in VALID_MESHES and context.object.data.nwo.face_props
    
    def execute(self, context):
        mesh = context.object.data
        nwo = mesh.nwo
        utils.delete_face_attribute(mesh, nwo.face_props_active_index, False)
        return {"FINISHED"}

class NWO_OT_FaceAttributeSelect(bpy.types.Operator):
    bl_idname = "nwo.face_attribute_select"
    bl_label = "Select"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(self, context):
        return context.object and context.object.type in VALID_MESHES and context.object.data.nwo.face_props and context.mode == 'EDIT_MESH'

    select: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        utils.select_face_attribute_edit_mode(context.object.data, self.select)
        return {"FINISHED"}


class NWO_OT_FaceAttributeMove(bpy.types.Operator):
    bl_idname = "nwo.face_attribute_move"
    bl_label = "Move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.EnumProperty(
        name="Direction",
        items=(("UP", "UP", "UP"), ("DOWN", "DOWN", "DOWN")),
        default="UP",
    )

    @classmethod
    def poll(self, context):
        return context.object and context.object.type in VALID_MESHES and len(context.object.data.nwo.face_props) > 1

    def execute(self, context):
        ob = context.object
        nwo = ob.data.nwo
        face_attributes = nwo.face_props
        active_index = nwo.face_props_active_index
        delta = {
            "DOWN": 1,
            "UP": -1,
        }[self.direction]

        to_index = (active_index + delta) % len(face_attributes)

        face_attributes.move(active_index, to_index)
        nwo.face_props_active_index = to_index

        return {"FINISHED"}
    
class NWO_MT_FacePropOperatorsMenu(bpy.types.Menu):
    bl_label = "Face Property Operators"
    bl_idname = "NWO_MT_FacePropOperatorsMenu"
    
    @classmethod
    def poll(self, context):
        return context.object and context.object.type in VALID_MESHES and context.object.data.nwo.face_props and context.mode != 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.operator("nwo.face_prop_copy_to_selected", icon='COPYDOWN')
        layout.operator("nwo.face_props_copy_to_selected", icon='COPYDOWN')
        layout.operator("nwo.add_emissive_node", icon='MATERIAL')
        
class NWO_OT_FacePropCopyToSelected(bpy.types.Operator):
    bl_idname = "nwo.face_prop_copy_to_selected"
    bl_label = "Copy Face Property to Selected"
    bl_description = "Copies the active face property to all selected objects. Where a face property is assigned to all objects, it will be assigned to faces on slected objects, otherwise matching face indices will be used to assign properties"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(self, context):
        return context.object and context.object.type in VALID_MESHES and context.object.data.nwo.face_props and len(context.selected_objects) > 1
    
    def execute(self, context):
        active = context.object
        mesh = active.data
        nwo = mesh.nwo
        
        prop = nwo.face_props[nwo.face_props_active_index]
        
        meshes = {ob.data for ob in context.selected_objects if ob != active and ob.type in VALID_MESHES}
        
        for me in meshes:
            utils.copy_face_prop(mesh, prop, me)
        
        self.report({'INFO'}, f"Copied {prop.name} to {len(meshes)} meshes")
        return {"FINISHED"}
            
class NWO_OT_FacePropsCopyToSelected(bpy.types.Operator):
    bl_idname = "nwo.face_props_copy_to_selected"
    bl_label = "Copy All Face Properties to Selected"
    bl_description = "Copies the all face properties to all selected objects. Where a face property is assigned to all objects, it will be assigned to faces on slected objects, otherwise matching face indices will be used to assign properties"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(self, context):
        return context.object and context.object.type in VALID_MESHES and context.object.data.nwo.face_props and len(context.selected_objects) > 1
    
    def execute(self, context):
        active = context.object
        mesh = active.data
        nwo = mesh.nwo
        meshes = {ob.data for ob in context.selected_objects if ob != active and ob.type in VALID_MESHES}
        
        for prop in nwo.face_props:
            for me in meshes:
                utils.copy_face_prop(mesh, prop, me)
        
        self.report({'INFO'}, f"Copied {len(nwo.face_props)} to {len(meshes)} meshes")
        return {"FINISHED"}
    
class NWO_OT_AddEmissiveNode(bpy.types.Operator):
    bl_idname = "nwo.add_emissive_node"
    bl_label = "Update Material for Emissives"
    bl_description = "Adds/updates an emissive node to show light emission from faces with the emissive property set"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH' and context.object.data.nwo.face_props and context.object.data.materials
    
    def execute(self, context):
        utils.setup_emissive_attributes(context.object.data)
        return {"FINISHED"}
        
def draw(op):
    if not op.batch:
        return
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_mask_set(False)
    gpu.state.depth_test_set('LESS_EQUAL')

    op.shader.bind()
    op.shader.uniform_float("color", (*op.color, op.alpha))
    op.batch.draw(op.shader)

    gpu.state.depth_test_set('NONE')
    gpu.state.depth_mask_set(True)
    gpu.state.blend_set('NONE')


class NWO_OT_FaceAttributeColorAll(bpy.types.Operator):
    bl_idname = "nwo.face_attribute_color_all"
    bl_label = "Highlight"
    bl_description = "Highlights faces with face properties based on their assigned color"

    enable_highlight: bpy.props.BoolProperty()
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == "MESH" and context.mode == 'EDIT_MESH'

    def execute(self, context):
        ob = context.object
        me = ob.data
        me.nwo.highlight = self.enable_highlight

        
        global int_highlight
        if int_highlight < 1000:
            int_highlight += 1
        else:
            int_highlight = 0
            
        poly_count = len(me.polygons)
                
        if self.enable_highlight:
            face_attributes = me.nwo.face_props
            for idx, prop in enumerate(face_attributes):
                if prop.face_count == poly_count:
                    continue
                bpy.ops.nwo.face_attribute_color(attribute_index=idx, highlight=int_highlight)

        return {"FINISHED"}


class NWO_OT_FaceAttributeColor(bpy.types.Operator):
    bl_idname  = "nwo.face_attribute_color"
    bl_label   = "Highlight"
    bl_options = {'INTERNAL'}

    attribute_index: bpy.props.IntProperty()
    highlight:       bpy.props.IntProperty()

    @staticmethod
    def calc_loops(bm):
        """Return loop triangles list (re‑computed each time)."""
        return bm.calc_loop_triangles()

    @staticmethod
    def tag_redraw():
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

    def shader_prep(self, context):
        self.shader = gpu.shader.from_builtin("UNIFORM_COLOR")

        bm = bmesh.from_edit_mesh(self.me)
        self.volume = bm.calc_volume()

        cm = bm.copy()
        cm.normal_update()
        scene_nwo = utils.get_scene_props()
        offset = 0.005 if scene_nwo.scale == 'max' else 0.0005
        for v in cm.verts:
            v.co += v.normal * offset
            
        bmesh.ops.transform(cm, matrix=context.object.matrix_world, verts=cm.verts)

        self.attribute = cm.faces.layers.bool.get(self.attribute_name)
        if self.attribute is None:
            self.report({'WARNING'},
                        f"Face attribute {self.attribute_name!r} not found")
            cm.free()
            return False

        loops = self.calc_loops(cm)
        self.verts = [
            loop.vert.co.to_tuple()
            for tri in loops
            if tri[0].face.hide is False and tri[0].face[self.attribute]
            for loop in tri
        ]

        if self.verts:
            self.batch = batch_for_shader(self.shader, "TRIS", {"pos": self.verts})

        cm.free()
        return True

    def modal(self, context, event):
        edit_mode = context.mode == "EDIT_MESH"

        if edit_mode:
            bm = bmesh.from_edit_mesh(self.me)
            bm_volume = bm.calc_volume()
        else:
            bm_volume = self.volume

        if event.type in {"G", "S", "R", "E", "K", "B", "I", "V"} \
           or event.value == "CLICK_DRAG":
            self.alpha = 0
        else:
            self.alpha = 0.25

        global int_highlight
        kill = (
            not edit_mode
            or self.highlight != int_highlight
            or self.attribute is None
            or not self.me.nwo.highlight
            or not self.me.nwo.face_props
        )

        if kill or bm_volume != self.volume:
            bpy.types.SpaceView3D.draw_handler_remove(self.handler, "WINDOW")
            self.tag_redraw()
            return {'FINISHED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        self.ob = context.object
        self.me = self.ob.data

        prop = self.me.nwo.face_props[self.attribute_index]
        self.attribute_name = prop.attribute_name
        self.color = prop.color
        self.alpha = 0
        self.batch = None

        if not self.shader_prep(context):
            return {'CANCELLED'}

        if self.verts:
            self.handler = bpy.types.SpaceView3D.draw_handler_add(
                draw, (self,), "WINDOW", "POST_VIEW"
            )
            context.window_manager.modal_handler_add(self)

            # toggle Edit mode twice to ensure redraw
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            return {'RUNNING_MODAL'}

        return {'CANCELLED'}


class NWO_OT_RegionListFace(bpy.types.Operator):
    bl_idname = "nwo.face_region_list"
    bl_label = "Region List"
    bl_description = "Applies a region to the selected face layer"

    def regions_items(self, context):
        items = []
        scene_nwo = utils.get_scene_props()
        for r in scene_nwo.regions_table:
            items.append((r.name, r.name, ''))
        return items

    region: bpy.props.EnumProperty(
        name="Region",
        items=regions_items,
    )

    def execute(self, context):
        nwo = context.object.data.nwo
        nwo.face_props[nwo.face_props_active_index].region_name = self.region
        return {"FINISHED"}


class NWO_OT_GlobalMaterialRegionListFace(NWO_OT_RegionListFace):
    bl_idname = "nwo.face_global_material_regions_list"
    bl_label = "Collision Material List"
    bl_description = "Applies a global material to the selected face layer"
    
    type: bpy.props.StringProperty()

    def execute(self, context):
        ob = context.object
        material = ob.active_material
        if self.type == 'FACE':
            ob.data.nwo.face_props[ob.data.nwo.face_props_active_index].global_material = self.region
        else:
            material.nwo.material_props[material.nwo.material_props_active_index].global_material = self.region
        return {"FINISHED"}

class NWO_OT_GlobalMaterialMenuFace(bpy.types.Menu):
    bl_label = "Add Collision Material"
    bl_idname = "NWO_MT_AddGlobalMaterialFace"

    def draw(self, context):
        layout = self.layout
        if utils.poll_ui(("model", "sky")):
            layout.operator_menu_enum(
                "nwo.face_global_material_regions_list",
                property="region",
                text="From Region",
            ).type = 'FACE'

        if utils.poll_ui(("scenario", "prefab", "model")):
            layout.operator(
                "nwo.global_material_globals",
                text="From Globals",
                icon="VIEWZOOM",
            ).face_level = 'FACE'
            
class NWO_OT_GlobalMaterialMenuMaterial(bpy.types.Menu):
    bl_label = "Add Collision Material"
    bl_idname = "NWO_MT_AddGlobalMaterialMaterial"

    def draw(self, context):
        layout = self.layout
        if utils.poll_ui(("model", "sky")):
            layout.operator_menu_enum(
                "nwo.face_global_material_regions_list",
                property="region",
                text="From Region",
            ).type = 'MATERIAL'

        if utils.poll_ui(("scenario", "prefab", "model")):
            layout.operator(
                "nwo.global_material_globals",
                text="From Globals",
                icon="VIEWZOOM",
            ).type = 'MATERIAL'
            
global_mats_items = []

# SETS MENUS
class NWO_MT_RegionsMenu(bpy.types.Menu):
    bl_label = "Regions"
    bl_idname = "NWO_MT_Regions"

    @classmethod
    def poll(self, context):
        return context.object

    def draw(self, context):
        layout = self.layout
        scene_nwo = utils.get_scene_props()
        is_scenario = scene_nwo.asset_type == 'scenario'
        region_names = [region.name for region in scene_nwo.regions_table if region.set_type == 'DEFAULT' or region.set_type == utils.set_type_from_asset(scene_nwo)]
        for r_name in region_names:
            layout.operator("nwo.region_assign_single", text=r_name).name = r_name

        layout.operator("nwo.region_add", text="New BSP" if is_scenario else "New Region", icon='ADD').set_object_prop = 1
        
class NWO_MT_RegionsMenuSelection(NWO_MT_RegionsMenu):
    bl_idname = "NWO_MT_RegionsSelection"
    
    def draw(self, context):
        layout = self.layout
        scene_nwo = utils.get_scene_props()
        is_scenario = scene_nwo.asset_type == 'scenario'
        region_names = [region.name for region in scene_nwo.regions_table if region.set_type == 'DEFAULT' or region.set_type == utils.set_type_from_asset(scene_nwo)]
        for r_name in region_names:
            layout.operator("nwo.region_assign", text=r_name).name = r_name
            
        layout.operator("nwo.region_add", text="New BSP" if is_scenario else "New Region", icon='ADD').set_object_prop = 2

class NWO_MT_FaceRegionsMenu(bpy.types.Menu):
    bl_label = "Regions"
    bl_idname = "NWO_MT_FaceRegions"

    @classmethod
    def poll(self, context):
        return context.object

    def draw(self, context):
        layout = self.layout
        scene_nwo = utils.get_scene_props()
        region_names = [region.name for region in scene_nwo.regions_table if region.set_type == 'DEFAULT' or region.set_type == utils.set_type_from_asset(scene_nwo)]
        for r_name in region_names:
            layout.operator("nwo.face_region_assign_single", text=r_name).name = r_name

        layout.operator("nwo.face_region_add", text="New Region", icon='ADD').set_object_prop = 1
        
class NWO_MT_MaterialRegionsMenu(bpy.types.Menu):
    bl_label = "Regions"
    bl_idname = "NWO_MT_MaterialRegions"

    @classmethod
    def poll(self, context):
        return context.object and context.object.active_material

    def draw(self, context):
        layout = self.layout
        scene_nwo = utils.get_scene_props()
        region_names = [region.name for region in scene_nwo.regions_table if region.set_type == 'DEFAULT' or region.set_type == utils.set_type_from_asset(scene_nwo)]
        for r_name in region_names:
            layout.operator("nwo.material_region_assign_single", text=r_name).name = r_name

        layout.operator("nwo.material_region_add", text="New Region", icon='ADD').set_object_prop = 1

class NWO_MT_SeamBackfaceMenu(NWO_MT_RegionsMenu):
    bl_idname = "NWO_MT_SeamBackface"

    def draw(self, context):
        layout = self.layout
        scene_nwo = utils.get_scene_props()
        region_names = [region.name for region in scene_nwo.regions_table if (region.name != utils.true_region(context.object.nwo) and region.set_type == 'DEFAULT' or region.set_type == utils.set_type_from_asset(scene_nwo))]
        if not region_names:
            layout.label(text="Only one BSP in scene. At least two required to use seams", icon="ERROR")
        for r_name in region_names:
            layout.operator("nwo.seam_backface_assign_single", text=r_name).name = r_name

class NWO_MT_PermutationsMenu(bpy.types.Menu):
    bl_label = "Permutations"
    bl_idname = "NWO_MT_Permutations"

    @classmethod
    def poll(self, context):
        return context.object

    def draw(self, context):
        layout = self.layout
        scene_nwo = utils.get_scene_props()
        is_scenario = scene_nwo.asset_type in ('scenario', 'prefab')
        permutation_names = [permutation.name for permutation in scene_nwo.permutations_table if permutation.set_type == 'DEFAULT' or permutation.set_type == utils.set_type_from_asset(scene_nwo)]
        for p_name in permutation_names:
            layout.operator("nwo.permutation_assign_single", text=p_name).name = p_name

        layout.operator("nwo.permutation_add", text="New BSP Layer" if is_scenario else "New Permutation", icon='ADD').set_object_prop = 1
        
class NWO_MT_PermutationsMenuSelection(NWO_MT_PermutationsMenu):
    bl_idname = "NWO_MT_PermutationsSelection"
    
    def draw(self, context):
        layout = self.layout
        scene_nwo = utils.get_scene_props()
        is_scenario = scene_nwo.asset_type in ('scenario', 'prefab')
        permutation_names = [permutation.name for permutation in scene_nwo.permutations_table if permutation.set_type == 'DEFAULT' or permutation.set_type == utils.set_type_from_asset(scene_nwo)]
        for p_name in permutation_names:
            layout.operator("nwo.permutation_assign", text=p_name).name = p_name
            
        layout.operator("nwo.permutation_add", text="New BSP Layer" if is_scenario else "New Permutation", icon='ADD').set_object_prop = 2

class NWO_MT_MarkerPermutationsMenu(bpy.types.Menu):
    bl_label = "Marker Permutations"
    bl_idname = "NWO_MT_MarkerPermutations"

    @classmethod
    def poll(self, context):
        return context.object

    def draw(self, context):
        layout = self.layout
        scene_nwo = utils.get_scene_props()
        permutation_names = [permutation.name for permutation in scene_nwo.permutations_table if permutation.set_type == 'DEFAULT' or permutation.set_type == utils.set_type_from_asset(scene_nwo)]
        for p_name in permutation_names:
            layout.operator("nwo.marker_perm_add", text=p_name).name = p_name

# Object Type Menu
class NWO_MT_MeshTypes(bpy.types.Menu):
    bl_label = "Mesh Type"
    bl_idname = "NWO_MT_MeshTypes"
    bl_description = "Mesh Type"
    
    @classmethod
    def poll(cls, context):
        return context.object and utils.is_mesh(context.object)
    
    def draw(self, context):
        layout = self.layout
        h4 = utils.is_corinth(context)
        if utils.poll_ui(("model", "multi_model")):
            layout.operator('nwo.apply_type_mesh_single', text='Render', icon_value=get_icon_id('render')).m_type = 'render'
            layout.operator('nwo.apply_type_mesh_single', text='Collision', icon_value=get_icon_id('collider')).m_type = 'collision'
            layout.operator('nwo.apply_type_mesh_single', text='Physics', icon_value=get_icon_id('physics')).m_type = 'physics'
            layout.operator('nwo.apply_type_mesh_single', text='Instanced Object', icon_value=get_icon_id('instance')).m_type = 'io'
        if utils.poll_ui(("scenario",)):
            layout.operator('nwo.apply_type_mesh_single', text='Instanced Geometry', icon_value=get_icon_id('instance')).m_type = 'instance'
            layout.operator('nwo.apply_type_mesh_single', text='Structure', icon_value=get_icon_id('structure')).m_type = 'structure'
            layout.operator('nwo.apply_type_mesh_single', text='Seam', icon_value=get_icon_id('seam')).m_type = 'seam'
            layout.operator('nwo.apply_type_mesh_single', text='Portal', icon_value=get_icon_id('portal')).m_type = 'portal'
            layout.operator('nwo.apply_type_mesh_single', text='Water', icon_value=get_icon_id('water')).m_type = 'water_surface'
            layout.operator('nwo.apply_type_mesh_single', text='Boundary Surface', icon_value=get_icon_id('soft_ceiling')).m_type = 'boundary_surface'
            layout.operator('nwo.apply_type_mesh_single', text='Lightmap Region', icon_value=get_icon_id('lightmap')).m_type = 'lightmap_region'
            if h4:
                layout.operator('nwo.apply_type_mesh_single', text='Bounding Box', icon_value=get_icon_id('volume')).m_type = 'obb_volume'
            else:
                layout.operator('nwo.apply_type_mesh_single', text='Rain Blocker', icon_value=get_icon_id('rain_blocker')).m_type = 'rain_blocker'
                layout.operator('nwo.apply_type_mesh_single', text='Rain Sheet', icon_value=get_icon_id('rain_sheet')).m_type = 'rain_sheet'
                layout.operator('nwo.apply_type_mesh_single', text='Pathfinding Cutout Volume', icon_value=get_icon_id('cookie_cutter')).m_type = 'cookie_cutter'
                layout.operator('nwo.apply_type_mesh_single', text='Fog Sheet', icon_value=get_icon_id('fog')).m_type = 'fog'
        elif utils.poll_ui(("prefab", "multi_prefab")):
            layout.operator('nwo.apply_type_mesh_single', text='Instanced Geometry', icon_value=get_icon_id('instance')).m_type = 'instance'
            
class NWO_MT_MarkerTypes(bpy.types.Menu):
    bl_label = "Marker Type"
    bl_idname = "NWO_MT_MarkerTypes"
    
    @classmethod
    def poll(self, context):
        return context.object and utils.is_marker(context.object)
    
    def draw(self, context):
        layout = self.layout
        h4 = utils.is_corinth(context)
        if utils.poll_ui(("model", "sky")):
            layout.operator('nwo.apply_type_marker_single', text='Model Marker', icon_value=get_icon_id('marker')).m_type = 'model'
            layout.operator('nwo.apply_type_marker_single', text='Effects', icon_value=get_icon_id('effects')).m_type = 'effects'
            if utils.poll_ui("model"):
                layout.operator('nwo.apply_type_marker_single', text='Garbage', icon_value=get_icon_id('garbage')).m_type = 'garbage'
                layout.operator('nwo.apply_type_marker_single', text='Hint', icon_value=get_icon_id('hint')).m_type = 'hint'
                layout.operator('nwo.apply_type_marker_single', text='Pathfinding Sphere', icon_value=get_icon_id('pathfinding_sphere')).m_type = 'pathfinding_sphere'
                layout.operator('nwo.apply_type_marker_single', text='Physics Constraint', icon_value=get_icon_id('physics_constraint')).m_type = 'physics_constraint'
                layout.operator('nwo.apply_type_marker_single', text='Target', icon_value=get_icon_id('target')).m_type = 'target'
                if h4:
                    layout.operator('nwo.apply_type_marker_single', text='Airprobe', icon_value=get_icon_id('airprobe')).m_type = 'airprobe'
        if utils.poll_ui(("scenario", "prefab")):
            layout.operator('nwo.apply_type_marker_single', text='Structure Marker', icon_value=get_icon_id('marker')).m_type = 'model'
            layout.operator('nwo.apply_type_marker_single', text='Game Object', icon_value=get_icon_id('game_object')).m_type = 'game_instance'
            if h4:
                layout.operator('nwo.apply_type_marker_single', text='Airprobe', icon_value=get_icon_id('airprobe')).m_type = 'airprobe'
                layout.operator('nwo.apply_type_marker_single', text='Light Cone', icon_value=get_icon_id('light_cone')).m_type = 'lightcone'

class NWO_OT_FaceDefaultsToggle(bpy.types.Operator):
    bl_idname = "nwo.toggle_defaults"
    bl_label = "Toggle Defaults"
    bl_description = "Toggles the default Face Properties display"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "MESH"
            and context.object.mode in ("OBJECT", "EDIT")
        )

    def execute(self, context):
        context.object.nwo.toggle_face_defaults = (
            not context.object.nwo.toggle_face_defaults
        )

        return {"FINISHED"}

class NWO_MT_GlobalMaterialMenu(bpy.types.Menu):
    bl_label = "Add Collision Material"
    bl_idname = "NWO_MT_AddGlobalMaterial"

    def draw(self, context):
        layout = self.layout
        if utils.poll_ui(("model", "sky")):
            layout.operator_menu_enum(
                "nwo.global_material_regions_list",
                property="region",
                text="From Region",
            )

        if utils.poll_ui(("scenario", "prefab", "model")):
            layout.operator(
                "nwo.global_material_globals",
                text="From Globals",
                icon="VIEWZOOM",
            )


class NWO_OT_RegionList(bpy.types.Operator):
    bl_idname = "nwo.region_list"
    bl_label = "Region List"
    bl_description = "Applies a region to the selected object"

    def regions_items(self, context):
        # get scene regions
        items = []
        scene_nwo = utils.get_scene_props()
        for r in scene_nwo.regions_table:
            items.append((r.name, r.name, ''))
        return items

    region: bpy.props.EnumProperty(
        name="Region",
        items=regions_items,
    )

    def execute(self, context):
        context.object.nwo.region_name = self.region
        return {"FINISHED"}


class NWO_OT_GlobalMaterialRegionList(NWO_OT_RegionList):
    bl_idname = "nwo.global_material_regions_list"
    bl_label = "Physics Material List"
    bl_description = "Applies a global material to the selected object"

    def execute(self, context):
        context.object.nwo.global_material = self.region
        return {"FINISHED"}
    
class NWO_OT_GlobalMaterialGlobals(NWO_OT_RegionList):
    bl_idname = "nwo.global_material_globals"
    bl_label = "Collision Material List"
    bl_description = "Applies a global material to the selected object"
    bl_property = "material"
    
    type: bpy.props.StringProperty()

    def get_materials(self, context):
        global global_mats_items
        if global_mats_items:
            return global_mats_items
        global_mats_items = []
        with GlobalsTag(path=Path('globals', 'globals.globals'), tag_must_exist=True) as globals:
            global_materials = globals.get_global_materials()

        global_materials.sort()
        for mat in global_materials:
            global_mats_items.append((mat, mat, ""))

        return global_mats_items
            
    material : bpy.props.EnumProperty(
        items=get_materials,
    )

    def execute(self, context):
        ob = context.object
        material = ob.active_material
        match self.type:
            case 'FACE':
                ob.data.nwo.face_props[ob.data.nwo.face_props_active_index].global_material = self.material
            case 'MATERIAL':
                material.nwo.material_props[material.nwo.material_props_active_index].global_material = self.material
            case _:
                ob.nwo.global_material = self.material
        context.area.tag_redraw()
        return {"FINISHED"}
    
    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'material', text="Global Material")

class NWO_OT_GlobalMaterialList(bpy.types.Operator):
    bl_idname = "nwo.global_material_list"
    bl_label = "Global Material List"
    bl_description = "Applies a Global Material to the selected object"
    bl_options = {'REGISTER', 'UNDO'}

    def global_material_items(self, context):
        # get scene regions
        global_materials = ["default"]
        for ob in utils.export_objects_mesh_only():
            global_material = ob.data.nwo.face_global_material
            if (
                global_material != ""
                and global_material not in global_materials
                and global_material
            ):
                global_materials.append(global_material)
            # also need to loop through face props
            if ob.type == "MESH":
                for face_prop in ob.data.nwo.face_props:
                    if (
                        face_prop.face_global_material != ""
                        and face_prop.face_global_material_override
                        and face_prop.face_global_material not in global_materials
                    ):
                        global_materials.append(face_prop.face_global_material)

        global_materials = utils.sort_alphanum(global_materials)
        items = []
        for index, global_material in enumerate(global_materials):
            items.append(utils.bpy_enum_list(global_material, index))

        return items

    global_material: bpy.props.EnumProperty(
        name="Collision Material",
        items=global_material_items,
    )

    def execute(self, context):
        context.object.data.nwo.face_global_material = self.global_material
        return {"FINISHED"}

class NWO_OT_PermutationList(bpy.types.Operator):
    bl_idname = "nwo.permutation_list"
    bl_label = "Permutation List"
    bl_description = "Applies a permutation to the selected object"
    bl_options = {'REGISTER', 'UNDO'}

    def permutations_items(self, context):
        # get scene perms
        permutations = ["default"]
        for ob in utils.export_objects_no_arm():
            permutation = utils.true_permutation(ob.nwo)
            if permutation not in permutations:
                permutations.append(permutation)

        permutations = utils.sort_alphanum(permutations)
        items = []
        for index, permutation in enumerate(permutations):
            items.append(utils.bpy_enum_list(permutation, index))

        return items

    permutation: bpy.props.EnumProperty(
        name="Permutation",
        items=permutations_items,
    )

    def execute(self, context):
        context.object.nwo.permutation_name = self.permutation
        return {"FINISHED"}


class NWO_OT_BSPList(bpy.types.Operator):
    bl_idname = "nwo.bsp_list"
    bl_label = "BSP List"
    bl_description = "Applies a BSP to the selected object"
    bl_options = {'REGISTER', 'UNDO'}

    def bsp_items(self, context):
        # get scene perms
        bsps = ["default"]
        for ob in utils.export_objects_no_arm():
            bsp = utils.true_region(ob.nwo)
            if bsp not in bsps:
                bsps.append(bsp)

        bsps = utils.sort_alphanum(bsps)
        items = []
        for index, bsp in enumerate(bsps):
            items.append(utils.bpy_enum_list(bsp, index))

        return items

    bsp: bpy.props.EnumProperty(
        name="bsp",
        items=bsp_items,
    )

    def execute(self, context):
        context.object.nwo.bsp_name_ui = self.bsp
        return {"FINISHED"}

class NWO_OT_BSPListSeam(NWO_OT_BSPList):
    bl_idname = "nwo.bsp_list_seam"

    def bsp_items(self, context):
        # get scene perms
        self_bsp = utils.true_region(context.object.nwo)
        bsps = []
        for ob in utils.export_objects_no_arm():
            bsp = utils.true_region(ob.nwo)
            if bsp != self_bsp and bsp not in bsps:
                bsps.append(bsp)

        bsps = utils.sort_alphanum(bsps)
        items = []
        for index, bsp in enumerate(bsps):
            items.append(utils.bpy_enum_list(bsp, index))

        return items

    bsp: bpy.props.EnumProperty(
        name="bsp",
        items=bsp_items,
    )

    def execute(self, context):
        context.object.nwo.seam_back = self.bsp
        return {"FINISHED"}

## MARKER PERM UI LIST
class NWO_UL_MarkerPermutations(bpy.types.UIList):
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
        layout.label(text=item.name, icon_value=get_icon_id("permutation"))

class NWO_OT_List_Add_MarkerPermutation(bpy.types.Operator):
    bl_idname = "nwo.marker_perm_add"
    bl_label = "Add"
    bl_description = "Add a new permutation"
    bl_options = {"UNDO"}

    name: bpy.props.StringProperty()

    def execute(self, context):
        ob = context.object
        nwo = ob.nwo
        for perm in nwo.marker_permutations:
            if perm.name == self.name:
                return {"CANCELLED"}
            
        bpy.ops.uilist.entry_add(
            list_path="object.nwo.marker_permutations",
            active_index_path="object.nwo.marker_permutations_index",
        )

        nwo.marker_permutations[nwo.marker_permutations_index].name = self.name
        context.area.tag_redraw()

        return {"FINISHED"}


class NWO_OT_List_Remove_MarkerPermutation(bpy.types.Operator):
    bl_idname = "nwo.marker_perm_remove"
    bl_label = "Remove"
    bl_description = "Remove a permutation from the list."
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and ob.nwo.marker_permutations

    def execute(self, context):
        ob = context.object
        nwo = ob.nwo
        nwo.marker_permutations.remove(nwo.marker_permutations_index)
        if nwo.marker_permutations_index > len(nwo.marker_permutations) - 1:
            nwo.marker_permutations_index += -1
        return {"FINISHED"}

## ACTOR ATTACHMENT UI LIST
def _active_actor_attachment(nwo):
    if not nwo.attachments:
        return None

    index = min(max(nwo.active_attachment_index, 0), len(nwo.attachments) - 1)
    return nwo.attachments[index]

def _actor_attachment_marker_items_from_tag_path(tag_path):
    try:
        with ObjectTag(path=tag_path) as object_tag:
            model_tag = object_tag.get_model_tag_path()
        if not model_tag or not Path(utils.get_tags_path(), model_tag).exists():
            return [("", "None", "")]
        with ModelTag(path=model_tag) as model:
            render_tag = model.get_render_model()
        if not render_tag or not Path(utils.get_tags_path(), render_tag).exists():
            return [("", "None", "")]
        with RenderModelTag(path=render_tag) as render:
            markers = render.get_markers()
    except (AttributeError, TypeError, ValueError, RuntimeError, FileNotFoundError):
        return [("", "None", "")]

    if not markers:
        return [("", "None", "")]

    return [(marker, marker, "") for marker in markers]

class NWO_UL_ActorAttachments(bpy.types.UIList):
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
        if item.marker_name:
            text = item.marker_name
        elif item.attachment_type:
            text = Path(item.attachment_type).with_suffix("").name
        else:
            text = f"Attachment {index + 1}"

        layout.label(text=text, icon='HIDE_ON' if item.invisible else 'HIDE_OFF')

class NWO_OT_ActorAttachmentAdd(bpy.types.Operator):
    bl_idname = "nwo.actor_attachment_add"
    bl_label = "Add"
    bl_description = "Add a new actor attachment"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        nwo = context.object.nwo
        item = nwo.attachments.add()
        item.name = f"attachment_{len(nwo.attachments)}"
        nwo.active_attachment_index = len(nwo.attachments) - 1
        context.area.tag_redraw()
        return {"FINISHED"}

class NWO_OT_ActorAttachmentRemove(bpy.types.Operator):
    bl_idname = "nwo.actor_attachment_remove"
    bl_label = "Remove"
    bl_description = "Remove the active actor attachment"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE' and context.object.nwo.attachments

    def execute(self, context):
        nwo = context.object.nwo
        nwo.attachments.remove(nwo.active_attachment_index)
        if nwo.active_attachment_index > len(nwo.attachments) - 1:
            nwo.active_attachment_index -= 1
        context.area.tag_redraw()
        return {"FINISHED"}

class NWO_OT_ActorAttachmentCopy(bpy.types.Operator):
    bl_idname = "nwo.actor_attachment_copy"
    bl_label = "Copy"
    bl_description = "Copy the active actor attachment"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE' and context.object.nwo.attachments

    def execute(self, context):
        nwo = context.object.nwo
        source = _active_actor_attachment(nwo)
        if source is None:
            return {"CANCELLED"}

        item = nwo.attachments.add()
        for prop in source.bl_rna.properties:
            identifier = prop.identifier
            if identifier == "rna_type" or prop.is_readonly:
                continue

            try:
                setattr(item, identifier, getattr(source, identifier))
            except (AttributeError, TypeError, ValueError, RuntimeError):
                pass

        item.name = f"{source.name}_copy" if source.name else f"attachment_{len(nwo.attachments)}"
        nwo.active_attachment_index = len(nwo.attachments) - 1
        context.area.tag_redraw()
        return {"FINISHED"}

class NWO_OT_ActorAttachmentMove(bpy.types.Operator):
    bl_idname = "nwo.actor_attachment_move"
    bl_label = ""
    bl_description = "Move the active actor attachment"
    bl_options = {"UNDO"}

    direction: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE' and len(context.object.nwo.attachments) > 1

    def execute(self, context):
        nwo = context.object.nwo
        table = nwo.attachments
        delta = {"down": 1, "up": -1}[self.direction]
        current_index = nwo.active_attachment_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        nwo.active_attachment_index = to_index
        context.area.tag_redraw()
        return {"FINISHED"}

class NWO_OT_GetActorAttachmentMarker(bpy.types.Operator):
    bl_idname = "nwo.get_actor_attachment_marker"
    bl_label = "Marker Names"
    bl_description = "Returns a list of model markers for the active actor attachment"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob is None or ob.type != 'ARMATURE' or not ob.nwo.attachments:
            return False
        if not ob.nwo.cinematic_object.strip() or not utils.current_project_valid():
            return False

        tag_path = Path(utils.get_tags_path(), utils.relative_path(ob.nwo.cinematic_object))
        return tag_path.is_absolute() and tag_path.exists() and tag_path.is_file()

    def marker_items(self, context):
        ob = context.object
        return _actor_attachment_marker_items_from_tag_path(ob.nwo.cinematic_object)

    marker: bpy.props.EnumProperty(
        name="Marker",
        items=marker_items,
    )

    def execute(self, context):
        item = _active_actor_attachment(context.object.nwo)
        if item is None:
            return {"CANCELLED"}

        item.marker_name = self.marker
        return {"FINISHED"}

class NWO_OT_GetActorAttachmentTypeMarker(bpy.types.Operator):
    bl_idname = "nwo.get_actor_attachment_type_marker"
    bl_label = "Attachment Marker Names"
    bl_description = "Returns a list of model markers for the active actor attachment type"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob is None or ob.type != 'ARMATURE' or not ob.nwo.attachments or not utils.current_project_valid():
            return False

        item = _active_actor_attachment(ob.nwo)
        if item is None or not item.attachment_type.strip():
            return False

        tag_path = Path(utils.get_tags_path(), utils.relative_path(item.attachment_type))
        return tag_path.is_absolute() and tag_path.exists() and tag_path.is_file()

    def marker_items(self, context):
        item = _active_actor_attachment(context.object.nwo)
        if item is None:
            return [("", "None", "")]

        return _actor_attachment_marker_items_from_tag_path(item.attachment_type)

    marker: bpy.props.EnumProperty(
        name="Marker",
        items=marker_items,
    )

    def execute(self, context):
        item = _active_actor_attachment(context.object.nwo)
        if item is None:
            return {"CANCELLED"}

        item.attachment_marker_name = self.marker
        return {"FINISHED"}
    
class NWO_OT_ShowWaterDirection(bpy.types.Operator):
    bl_idname = "nwo.show_water_direction"
    bl_label = "Show Water Direction"
    bl_description = "Temporarily replaces selected water object materials with arrows to indicate the direction of physical water flow. Requires material or rendered shading mode to be active"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        if context.selected_objects:
            for area in context.screen.areas:
                for space in area.spaces:
                    if space.type == 'VIEW_3D' and space.shading.type in {'MATERIAL', 'RENDERED'}:
                        return True
        return False

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        if scene_nwo.show_water_direction:
            scene_nwo.show_water_direction = False
            return {"FINISHED"}
        else:
            scene_nwo.show_water_direction = True
            self.ob_mats = defaultdict(list)
            self.objects: set[bpy.types.Object] = {ob for ob in context.selected_objects if ob.type in VALID_MESHES and ob.data.nwo.mesh_type == '_connected_geometry_mesh_type_water_surface'}
            self.set_materials()
            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}
    
    def set_materials(self):
        water_material = bpy.data.materials.get("WaterDirection")
        if water_material is None:
            lib_blend = Path(utils.MATERIAL_RESOURCES, 'shared_nodes.blend')
            with bpy.data.libraries.load(str(lib_blend), link=False) as (_, data_to):
                data_to.materials = ["WaterDirection"]
                
            water_material = bpy.data.materials["WaterDirection"]
            
        for ob in self.objects:
            if ob.material_slots:
                for slot in ob.material_slots:
                    self.ob_mats[ob].append(slot.material)
                    slot.material = water_material
            else:
                self.ob_mats[ob] = []
                ob.data.materials.append(water_material)
    
    def restore_materials(self):
        for ob, materials in self.ob_mats.items():
            if materials:
                for slot, mat in zip(ob.material_slots, materials):
                    slot.material = mat 
            else:
                ob.data.materials.clear()

    def modal(self, context, event):
        scene_nwo = utils.get_scene_props()
        if scene_nwo.export_in_progress or not scene_nwo.show_water_direction:
            scene_nwo.show_water_direction = False
            self.restore_materials()
            return {"FINISHED"}
        
        return {'PASS_THROUGH'}
    
def draw_halo_attach(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("nwo.halo_attach")

parent_markers = []
child_markers = []

def _copy_marker_transform(target: bpy.types.Object, marker: bpy.types.Object):
    target.matrix_world = marker.matrix_world.copy()
    constraint = target.constraints.new(type='COPY_TRANSFORMS')
    constraint.target = marker
    return constraint
 
class NWO_OT_HaloAttach(bpy.types.Operator):
    bl_idname = "nwo.halo_attach"
    bl_label = "Attach Halo Armatures"
    bl_description = "Attach armatures together in the same way the game handles this. The selected armature will be attached to the active armature"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        if context.object and len(context.selected_objects) == 2:
            return all(ob.type == 'ARMATURE' for ob in context.selected_objects)
        
    def get_parent_marker(self, context):
        return utils.bpy_enum_from_list([ob.name for ob in parent_markers], True)

    parent_marker: bpy.props.EnumProperty(
        name="Parent Marker",
        description="Marker to parent the child armature to. If none, the child will be attached the parent armature directly",
        items=get_parent_marker,
    )
    
    def get_child_marker(self, context):
        return utils.bpy_enum_from_list([ob.name for ob in child_markers], True)
    
    child_marker: bpy.props.EnumProperty(
        name="Child Marker",
        description="Marker used to offset the parent-child relationship of the two armatures, as if the parent marker and child marker are attached directly. If none, the child armature will be attached directly to the parent marker (or parent armature if none)",
        items=get_child_marker,
    )
    
    def invoke(self, context, _):
        parent_skeleton = context.object
        child_skeleton = [ob for ob in context.selected_objects if ob is not parent_skeleton][0]
        
        global parent_markers
        global child_markers
        
        parent_markers = [ob for ob in parent_skeleton.children if utils.is_marker(ob)]
        child_markers = [ob for ob in child_skeleton.children if utils.is_marker(ob)]
        
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        parent_skeleton = context.object
        parent_marker = bpy.data.objects.get(self.parent_marker) if self.parent_marker != "none" else None
        
        child_skeleton = [ob for ob in context.selected_objects if ob is not parent_skeleton][0]
        child_marker = bpy.data.objects.get(self.child_marker) if self.child_marker != "none" else None
        
        has_marker_parent = parent_marker is not None
        has_marker_child = child_marker is not None
        
        child_skeleton.constraints.clear()
        if has_marker_child:
            child_marker.constraints.clear()
            
        child_skeleton.matrix_world = Matrix.Identity(4)

        if has_marker_child:
            attach_point = child_marker.copy()
            attach_point.name = f"{parent_skeleton.name}_attach"
            attach_point_matrix = attach_point.matrix_world.copy()
            attach_point.parent = None
            attach_point.matrix_world = attach_point_matrix
            attach_point.nwo.export_this = False
            
            for coll in child_marker.users_collection:
                coll.objects.link(attach_point)
            
            arm_matrix = child_skeleton.matrix_world.copy()
            child_skeleton.parent = attach_point
            child_skeleton.matrix_world = arm_matrix

        if has_marker_parent:
            if has_marker_child:
                _copy_marker_transform(attach_point, parent_marker)
            else:
                _copy_marker_transform(child_skeleton, parent_marker)
        else:
            if has_marker_child:
                attach_point.parent = parent_skeleton
                attach_point.matrix_world = parent_skeleton.matrix_world
            else:
                child_skeleton.parent = parent_skeleton
        
        self.report({'INFO'}, f"Attached {child_skeleton.name} to {parent_skeleton.name}")
                
        return {"FINISHED"}

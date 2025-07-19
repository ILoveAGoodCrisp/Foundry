"""Classes for Object Panel UI"""

from pathlib import Path
import bpy
import bmesh
from uuid import uuid4
import gpu
from gpu_extras.batch import batch_for_shader
import numpy as np

from ...constants import VALID_MESHES, face_prop_type_items, face_prop_descriptions

from ...icons import get_icon_id
from ... import utils

from ...managed_blam.globals import GlobalsTag

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
        children = len(ob.children_recursive)
        for child in ob.children_recursive:
            child.select_set(True)
        self.report({'INFO'}, f"Selected {len(children)} child objects")
        return {"FINISHED"}
    
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
                elif name == "region" and context.mode != 'EDIT_MESH':
                    continue
                elif name != 'global_material' and asset_type == "model" and context.object.data.nwo.mesh_type == '_connected_geometry_mesh_type_collision':
                    continue
                elif name == 'global_material' and asset_type == "model" and context.object.data.nwo.mesh_type != '_connected_geometry_mesh_type_collision':
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
        return context.object and context.object.type == "MESH" and bpy.ops.object.mode_set.poll()

    def execute(self, context):
        bpy.ops.object.editmode_toggle()
        return {"FINISHED"}


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
        
        item = nwo.face_props.add()
        nwo.face_props_active_index = len(nwo.face_props) - 1
        
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
            region = context.scene.nwo.regions_table[0].name
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
        ob = context.object
        if ob and ob.type == "MESH":
            nwo = ob.data.nwo
            return nwo.face_props
        return False

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

    # --------------------------------------------------------------
    #  Utilities
    # --------------------------------------------------------------
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

    # --------------------------------------------------------------
    #  Shader prep / shell mesh build
    # --------------------------------------------------------------
    def shader_prep(self, context):
        self.shader = gpu.shader.from_builtin("UNIFORM_COLOR")

        bm = bmesh.from_edit_mesh(self.me)
        self.volume = bm.calc_volume()

        # ----------------------------------------------------------
        #  Build a *shell* mesh where each vertex is displaced once
        # ----------------------------------------------------------
        cm = bm.copy()
        cm.normal_update()                       # ensure vertex normals
        offset = 0.001 if context.scene.nwo.scale == 'max' else 0.0001
        for v in cm.verts:
            v.co += v.normal * offset            # displaced exactly once
            
        bmesh.ops.transform(cm, matrix=context.object.matrix_world, verts=cm.verts)

        # ----------------------------------------------------------
        #  Extract vertices of faces that own the target attribute
        # ----------------------------------------------------------
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

    # --------------------------------------------------------------
    #  Modal logic
    # --------------------------------------------------------------
    def modal(self, context, event):
        edit_mode = context.mode == "EDIT_MESH"

        if edit_mode:
            bm = bmesh.from_edit_mesh(self.me)
            bm_volume = bm.calc_volume()
        else:
            bm_volume = self.volume

        # fade‑out while transform tools are active
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

    # --------------------------------------------------------------
    #  Operator entry point
    # --------------------------------------------------------------
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
            bpy.ops.object.editmode_toggle()
            bpy.ops.object.editmode_toggle()
            return {'RUNNING_MODAL'}

        return {'CANCELLED'}


class NWO_OT_RegionListFace(bpy.types.Operator):
    bl_idname = "nwo.face_region_list"
    bl_label = "Region List"
    bl_description = "Applies a region to the selected face layer"

    def regions_items(self, context):
        items = []
        for r in context.scene.nwo.regions_table:
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

    def execute(self, context):
        nwo = context.object.data.nwo
        nwo.face_props[nwo.face_props_active_index].global_material = self.region
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
            )

        if utils.poll_ui(("scenario", "prefab", "model")):
            layout.operator(
                "nwo.global_material_globals",
                text="From Globals",
                icon="VIEWZOOM",
            ).face_level = True
            
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
        is_scenario = context.scene.nwo.asset_type == 'scenario'
        region_names = [region.name for region in context.scene.nwo.regions_table]
        for r_name in region_names:
            layout.operator("nwo.region_assign_single", text=r_name).name = r_name

        layout.operator("nwo.region_add", text="New BSP" if is_scenario else "New Region", icon='ADD').set_object_prop = 1
        
class NWO_MT_RegionsMenuSelection(NWO_MT_RegionsMenu):
    bl_idname = "NWO_MT_RegionsSelection"
    
    def draw(self, context):
        layout = self.layout
        is_scenario = context.scene.nwo.asset_type == 'scenario'
        region_names = [region.name for region in context.scene.nwo.regions_table]
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
        region_names = [region.name for region in context.scene.nwo.regions_table]
        for r_name in region_names:
            layout.operator("nwo.face_region_assign_single", text=r_name).name = r_name

        layout.operator("nwo.face_region_add", text="New Region", icon='ADD').set_object_prop = 1

class NWO_MT_SeamBackfaceMenu(NWO_MT_RegionsMenu):
    bl_idname = "NWO_MT_SeamBackface"

    def draw(self, context):
        layout = self.layout
        region_names = [region.name for region in context.scene.nwo.regions_table if region.name != utils.true_region(context.object.nwo)]
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
        is_scenario = context.scene.nwo.asset_type in ('scenario', 'prefab')
        permutation_names = [permutation.name for permutation in context.scene.nwo.permutations_table]
        for p_name in permutation_names:
            layout.operator("nwo.permutation_assign_single", text=p_name).name = p_name

        layout.operator("nwo.permutation_add", text="New BSP Layer" if is_scenario else "New Permutation", icon='ADD').set_object_prop = 1
        
class NWO_MT_PermutationsMenuSelection(NWO_MT_PermutationsMenu):
    bl_idname = "NWO_MT_PermutationsSelection"
    
    def draw(self, context):
        layout = self.layout
        is_scenario = context.scene.nwo.asset_type in ('scenario', 'prefab')
        permutation_names = [permutation.name for permutation in context.scene.nwo.permutations_table]
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
        permutation_names = [permutation.name for permutation in context.scene.nwo.permutations_table]
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
        if utils.poll_ui("model"):
            layout.operator('nwo.apply_type_mesh_single', text='Render', icon_value=get_icon_id('model')).m_type = 'render'
            layout.operator('nwo.apply_type_mesh_single', text='Collision', icon_value=get_icon_id('collider')).m_type = 'collision'
            layout.operator('nwo.apply_type_mesh_single', text='Physics', icon_value=get_icon_id('physics')).m_type = 'physics'
            layout.operator('nwo.apply_type_mesh_single', text='Instanced Object', icon_value=get_icon_id('instance')).m_type = 'io'
        if utils.poll_ui("scenario"):
            layout.operator('nwo.apply_type_mesh_single', text='Instanced Geometry', icon_value=get_icon_id('instance')).m_type = 'instance'
            layout.operator('nwo.apply_type_mesh_single', text='Structure', icon_value=get_icon_id('structure')).m_type = 'structure'
            layout.operator('nwo.apply_type_mesh_single', text='Seam', icon_value=get_icon_id('seam')).m_type = 'seam'
            layout.operator('nwo.apply_type_mesh_single', text='Portal', icon_value=get_icon_id('portal')).m_type = 'portal'
            layout.operator('nwo.apply_type_mesh_single', text='Water Surface', icon_value=get_icon_id('water')).m_type = 'water_surface'
            layout.operator('nwo.apply_type_mesh_single', text='Boundary Surface', icon_value=get_icon_id('soft_ceiling')).m_type = 'boundary_surface'
            if h4:
                layout.operator('nwo.apply_type_mesh_single', text='Bounding Box', icon_value=get_icon_id('volume')).m_type = 'obb_volume'
            else:
                layout.operator('nwo.apply_type_mesh_single', text='Rain Blocker', icon_value=get_icon_id('rain_blocker')).m_type = 'rain_blocker'
                layout.operator('nwo.apply_type_mesh_single', text='Rain Sheet', icon_value=get_icon_id('rain_sheet')).m_type = 'rain_sheet'
                layout.operator('nwo.apply_type_mesh_single', text='Pathfinding Cutout Volume', icon_value=get_icon_id('cookie_cutter')).m_type = 'cookie_cutter'
                layout.operator('nwo.apply_type_mesh_single', text='Fog Sheet', icon_value=get_icon_id('fog')).m_type = 'fog'
        elif utils.poll_ui("prefab"):
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
        for r in context.scene.nwo.regions_table:
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
    
    face_level: bpy.props.BoolProperty()

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
        if self.face_level:
            ob.data.nwo.face_props[ob.data.nwo.face_props_active_index].global_material = self.material
        else:
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
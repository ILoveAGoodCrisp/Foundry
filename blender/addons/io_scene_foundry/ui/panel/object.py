"""Classes for Object Panel UI"""

from pathlib import Path
import bpy
import bmesh
from uuid import uuid4
import gpu
from gpu_extras.batch import batch_for_shader

from ...constants import VALID_MESHES

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

# FACE PROPERTIES #
class NWO_MT_FaceLayerAddMenu(bpy.types.Menu):
    bl_label = "Add Face Property"
    bl_idname = "NWO_MT_FaceLayerAdd"

    def __init__(self):
        self.op_prefix = "nwo.face_layer_add"

    def draw(self, context):
        layout = self.layout
        ob = context.object
        nwo = ob.nwo
        h4 = utils.is_corinth(context)
        if utils.poll_ui(("model", "sky")):
            layout.operator(self.op_prefix, text="Region").options = "region"
        # if (
        #     utils.poll_ui("scenario")
        #     and nwo.mesh_type == "_connected_geometry_mesh_type_default"
        # ):
        #     layout.operator(self.op_prefix, text="Seam").options = "seam"
        if (h4 and
            (nwo.mesh_type == "_connected_geometry_mesh_type_collision"
            or nwo.mesh_type == "_connected_geometry_mesh_type_physics"
            or nwo.mesh_type == "_connected_geometry_mesh_type_default"
            or (nwo.mesh_type == "_connected_geometry_mesh_type_structure" and utils.poll_ui(('scenario', 'prefab')))
        ) or (not h4 and nwo.mesh_type in ("_connected_geometry_mesh_type_physics", "_connected_geometry_mesh_type_collision"))):
            layout.operator(
                self.op_prefix, text="Collision Material"
            ).options = "face_global_material"
        if nwo.mesh_type in (
            "_connected_geometry_mesh_type_default",
            "_connected_geometry_mesh_type_structure",
            "_connected_geometry_mesh_type_collision",
        ):
            layout.operator(self.op_prefix, text="Two Sided").options = "two_sided"
            if nwo.mesh_type != '_connected_geometry_mesh_type_collision':
                layout.operator(self.op_prefix, text="Transparent").options = "transparent"
                if context.scene.nwo.asset_type in ('model', 'sky'):
                    layout.operator(self.op_prefix, text="Tessellation Density").options = "mesh_tessellation_density"
                    layout.operator(self.op_prefix, text="Draw Distance").options = "draw_distance"
        if utils.poll_ui(("model", "scenario", "prefab")):
            if nwo.mesh_type in (
                "_connected_geometry_mesh_type_default",
                "_connected_geometry_mesh_type_structure",
            ):
                layout.operator(
                    self.op_prefix, text="Uncompressed"
                ).options = "precise_position"
                
            if utils.poll_ui(("scenario", "prefab")) and nwo.mesh_type in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_structure', '_connected_geometry_mesh_type_collision'):
                if h4 and nwo.mesh_type != '_connected_geometry_mesh_type_collision':
                    layout.operator(
                        self.op_prefix, text="No Lightmap"
                    ).options = "no_lightmap"
                    layout.operator(
                        self.op_prefix, text="Lightmap Only"
                    ).options = "lightmap_only"
                    layout.operator(
                        self.op_prefix, text="No Visibility Culling"
                    ).options = "no_pvs"
                elif not h4:
                    layout.operator(
                        self.op_prefix, text="Ladder"
                    ).options = "ladder"
                    layout.operator(
                        self.op_prefix, text="Slip Surface"
                    ).options = "slip_surface"
                    layout.operator(
                        self.op_prefix, text="Breakable"
                    ).options = "breakable"
                if nwo.mesh_type != '_connected_geometry_mesh_type_collision':
                    layout.operator(
                        self.op_prefix, text="Decal Offset"
                    ).options = "decal_offset"
                    layout.operator(
                        self.op_prefix, text="No Shadow"
                    ).options = "no_shadow"
            elif utils.poll_ui(("model")):
                if nwo.mesh_type == '_connected_geometry_mesh_type_collision' and not h4:
                    layout.operator(
                        self.op_prefix, text="Ladder"
                    ).options = "ladder"
                    layout.operator(
                        self.op_prefix, text="Slip Surface"
                    ).options = "slip_surface"
                elif nwo.mesh_type != '_connected_geometry_mesh_type_collision':
                    layout.operator(
                        self.op_prefix, text="Decal Offset"
                    ).options = "decal_offset"

        if utils.poll_ui(("scenario", "prefab")):
            if nwo.mesh_type == "_connected_geometry_mesh_type_default":
                layout.operator(
                    self.op_prefix, text="Render Only"
                ).options = "render_only"
                layout.operator(
                    self.op_prefix, text="Collision Only"
                ).options = "collision_only"
                layout.operator(
                    self.op_prefix, text="Sphere Collision Only"
                ).options = "sphere_collision_only"
                if h4:
                    layout.operator(
                        self.op_prefix, text="Bullet Collision Only"
                    ).options = "bullet_collision_only"
                    layout.operator(
                        self.op_prefix, text="Player Collision Only"
                    ).options = "player_collision_only"
                layout.operator(
                    self.op_prefix, text="Emissive"
                ).options = "emissive"

                layout.operator_menu_enum(
                    self.op_prefix + "_lightmap",
                    property="options",
                    text="Lightmap",
                )


class NWO_MT_FacePropAddMenu(NWO_MT_FaceLayerAddMenu):
    bl_label = "Add Face Property"
    bl_idname = "NWO_MT_FacePropAdd"

    def __init__(self):
        self.op_prefix = "nwo.face_prop_add"


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
        face_layer = item
        if face_layer:
            row = layout.row()
            row.scale_x = 0.25
            row.prop(face_layer, "layer_color", text="")
            row = layout.row()
            row.prop(face_layer, "name", text="", emboss=False, icon_value=icon)
            row = layout.row()
            row.alignment = "RIGHT"
            f_count = item.face_count
            if f_count:
                row.label(text=f"{str(f_count)}  ")
            else:
                row.label(text=f"Not Assigned  ")
                
class NWO_OT_UpdateLayersFaceCount(bpy.types.Operator):
    bl_idname = "nwo.update_layers_face_count"
    bl_label = "Refresh Face Counts"
    bl_description = "Refreshes the face counts of all face property layers in case they are out of sync"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object

    def execute(self, context):
        if context.mode == "EDIT_MESH":
            bm = bmesh.from_edit_mesh(context.object.data)
        else:
            bm = bmesh.new()
            bm.from_mesh(context.object.data)

        for face_layer in context.object.data.nwo.face_props:
            face_layer.face_count = utils.layer_face_count(bm, bm.faces.layers.int.get(face_layer.layer_name))
            
        return {"FINISHED"}



def toggle_override(option, bool_var, item):
    match option:
        case "region":
            item.region_name_override = bool_var
        case "two_sided":
            item.face_two_sided_override = bool_var
        case "transparent":
            item.face_transparent_override = bool_var
        case "draw_distance":
            item.face_draw_distance_override = bool_var
        case "mesh_tessellation_density":
            item.mesh_tessellation_density_override = bool_var
        case "render_only":
            item.render_only_override = bool_var
        case "collision_only":
            item.collision_only_override = bool_var
        case "sphere_collision_only":
            item.sphere_collision_only_override = bool_var
        case "bullet_collision_only":
            item.bullet_collision_only_override = bool_var
        case "player_collision_only":
            item.player_collision_only_override = bool_var
        case "texcoord_usage":
            item.texcoord_usage_override = bool_var
        case "face_global_material":
            item.face_global_material_override = bool_var
        case "ladder":
            item.ladder_override = bool_var
        case "slip_surface":
            item.slip_surface_override = bool_var
        case "decal_offset":
            item.decal_offset_override = bool_var
        case "breakable":
            item.breakable_override = bool_var
        case "no_shadow":
            item.no_shadow_override = bool_var
        case "precise_position":
            item.precise_position_override = bool_var
        case "no_lightmap":
            item.no_lightmap_override = bool_var
        case "lightmap_only":
            item.lightmap_only_override = bool_var
        case "no_pvs":
            item.no_pvs_override = bool_var
        # instances
        case "instanced_collision":
            item.instanced_collision_override = bool_var
        case "instanced_physics":
            item.instanced_physics_override = bool_var
        case "cookie_cutter":
            item.cookie_cutter_override = bool_var
        # lightmap
        case "lightmap_additive_transparency":
            item.lightmap_additive_transparency_override = bool_var
        case "lightmap_resolution_scale":
            item.lightmap_resolution_scale_override = bool_var
        case "lightmap_type":
            item.lightmap_type_override = bool_var
        case "lightmap_analytical_bounce_modifier":
            item.lightmap_analytical_bounce_modifier_override = bool_var
        case "lightmap_general_bounce_modifier":
            item.lightmap_general_bounce_modifier_override = bool_var
        case "lightmap_translucency_tint_color":
            item.lightmap_translucency_tint_color_override = bool_var
        case "lightmap_lighting_from_both_sides":
            item.lightmap_lighting_from_both_sides_override = bool_var
        # material lighting
        case "emissive":
            item.emissive_override = bool_var


class NWO_OT_EditMode(bpy.types.Operator):
    """Toggles Edit Mode for face layer editing"""

    bl_idname = "nwo.edit_face_layers"
    bl_label = "Enter Edit Mode"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "MESH"
            and context.object.mode in ("OBJECT", "EDIT")
        )

    def execute(self, context):
        bpy.ops.object.mode_set(mode="EDIT", toggle=True)

        return {"FINISHED"}


class NWO_OT_FaceLayerAdd(bpy.types.Operator):
    bl_idname = "nwo.face_layer_add"
    bl_label = "Add Face Layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == "MESH" and context.mode == 'EDIT_MESH'

    new: bpy.props.BoolProperty(default=True)

    options: bpy.props.EnumProperty(
        default="region",
        items=[
            ("region", "Region", ""),
            ("emissive", "Emissive", ""),
            ("face_global_material", "Collision Material", ""),
            ("precise_position", "Precise Position", ""),
            ("two_sided", "Two Sided", ""),
            ("transparent", "Transparent", ""),
            ("draw_distance", "Draw Distance", ""),
            ("mesh_tessellation_density", "Tessellation Density", ""),
            ("render_only", "Render Only", ""),
            ("collision_only", "Collision Only", ""),
            ("sphere_collision_only", "Sphere Collision Only", ""),
            ("bullet_collision_only", "Bullet Collision Only", ""),
            ("player_collision_only", "Player Collision Only", ""),
            ("decal_offset", "Decal Offset", ""),
            ("no_shadow", "No Shadow", ""),
            ("ladder", "Ladder", ""),
            ("slip_surface", "Slip Surface", ""),
            ("breakable", "Breakable", ""),
            ("no_lightmap", "No Lightmap", ""),
            ("lightmap_only", "Lightmap Only", ""),
            ("no_pvs", "No Visibility Culling", ""),
        ],
    )

    fm_name: bpy.props.StringProperty()

    def add_face_layer(self, me, prefix):
        bm = bmesh.from_edit_mesh(me)
        face_layer = bm.faces.layers.int.new(f"{prefix}_{str(uuid4())}")
        # get list of selected faces
        for face in bm.faces:
            if face.select:
                face[face_layer] = 1

        bmesh.update_edit_mesh(me)
        return face_layer.name, utils.layer_face_count(bm, face_layer)

    def execute(self, context):
        ob = context.object
        nwo = ob.data.nwo
        print(self.options)
        match self.options:
            case "seam":
                self.fm_name = f"seam {utils.true_region(ob.nwo)}:"
            case "precise_position":
                self.fm_name = "Uncompressed"
            case "render_only":
                self.fm_name = "Render Only"
            case "collision_only":
                self.fm_name = "Collision Only"
            case "sphere_collision_only":
                self.fm_name = "Sphere Collision Only"
            case "bullet_collision_only":
                self.fm_name = "Bullet Collision Only"
            case "player_collision_only":
                self.fm_name = "Player Collision Only"
            case "two_sided":
                self.fm_name = "Two Sided"
            case "transparent":
                self.fm_name = "Transparent"
            case "draw_distance":
                self.fm_name = "Draw Distance"
            case "mesh_tessellation_density":
                self.fm_name = "Tesselation Density"
            case "ladder":
                self.fm_name = "Ladder"
            case "slip_surface":
                self.fm_name = "Slipsurface"
            case "breakable":
                self.fm_name = "Breakable"
            case "decal_offset":
                self.fm_name = "Decal Offset"
            case "no_shadow":
                self.fm_name = "No Shadow"
            case "no_lightmap":
                self.fm_name = "No Lightmap"
            case "lightmap_only":
                self.fm_name = "Lightmap Only"
            case "no_pvs":
                self.fm_name = "No PVS"
            # lightmap
            case "lightmap_additive_transparency":
                self.fm_name = "lightmap_additive_transparency"
            case "lightmap_resolution_scale":
                self.fm_name = "lightmap_resolution_scale"
            case "lightmap_type":
                self.fm_name = "lightmap_type"
            case "lightmap_analytical_bounce_modifier":
                self.fm_name = "lightmap_analytical_bounce_modifier"
            case "lightmap_general_bounce_modifier":
                self.fm_name = "lightmap_general_bounce_modifier"
            case "lightmap_translucency_tint_color":
                self.fm_name = "lightmap_translucency_tint_color"
            case "lightmap_lighting_from_both_sides":
                self.fm_name = "lightmap_lighting_from_both_sides"
            # material lighting
            case "emissive":
                self.fm_name = "Emissive"

        if self.fm_name == "":
            self.fm_name = "default"

        layer_name, face_count = self.add_face_layer(ob.data, self.fm_name)
        item = nwo.face_props.add()
        nwo.face_props_active_index = len(nwo.face_props) - 1

        toggle_override(self.options, True, item)

        item.name = self.fm_name
        item.layer_name = layer_name
        item.face_count = face_count
        item.layer_color = utils.random_color()
        if nwo.highlight:
            bpy.ops.nwo.face_layer_color_all(enable_highlight=nwo.highlight)

        if self.options == "region":
            region = context.scene.nwo.regions_table[0].name
            item.name = 'region::'
            item.region_name = region
        elif self.options == "face_global_material":
            item.name = 'material::'
            item.face_global_material = "default"
            
        context.area.tag_redraw()
        # gotta do this mess so undo states correctly register
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        bpy.ops.ed.undo_push()
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        row = layout.row()
        if self.options == "region":
            row.prop(self, "fm_name", text="Region")
            # row.operator_menu_enum("nwo.face_region_list", "region", text='', icon="DOWNARROW_HLT").dialog = True
        else:
            row.prop(self, "fm_name", text="Collision Material")
            # row.operator_menu_enum("nwo.face_global_material_list", "global_material", text='', icon="DOWNARROW_HLT").dialog = True


class NWO_OT_FaceLayerRemove(bpy.types.Operator):
    """Removes a face layer"""

    bl_idname = "nwo.face_layer_remove"
    bl_label = "Remove"
    bl_options = {"UNDO"}

    @classmethod
    def poll(self, context):
        ob = context.object
        if ob and ob.type == "MESH":
            nwo = ob.data.nwo
            return nwo.face_props
        return False

    def remove_face_layer(self, context, me, layer_name):
        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(me)
        else:
            bm = bmesh.new()
            bm.from_mesh(me)
        # get list of selected faces
        layer = bm.faces.layers.int.get(layer_name)
        if layer is not None:
            bm.faces.layers.int.remove(layer)
        
        if context.mode == 'EDIT_MESH':
            bmesh.update_edit_mesh(me)
        else:
            bm.to_mesh(me)

    def execute(self, context):
        ob = context.object
        nwo = ob.data.nwo
        item = nwo.face_props[nwo.face_props_active_index]
        self.remove_face_layer(context, ob.data, item.layer_name)
        nwo.face_props.remove(nwo.face_props_active_index)
        if nwo.face_props_active_index > len(nwo.face_props) - 1:
            nwo.face_props_active_index += -1
        if nwo.highlight:
            bpy.ops.nwo.face_layer_color_all(enable_highlight=nwo.highlight)

        context.area.tag_redraw()
        # gotta do this mess so undo states correActly register
        if context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
            bpy.ops.ed.undo_push()
            bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        return {"FINISHED"}


class NWO_OT_FaceLayerAssign(bpy.types.Operator):
    bl_idname = "nwo.face_layer_assign"
    bl_label = "Remove"
    bl_options = {'UNDO'}

    assign: bpy.props.BoolProperty(default=True)

    def edit_layer(self, me, layer_name):
        bm = bmesh.from_edit_mesh(me)
        # get list of selected faces
        face_layer = bm.faces.layers.int.get(layer_name)
        if face_layer is None:
            face_layer = bm.faces.layers.int.new(layer_name)
        for face in bm.faces:
            if face.select:
                face[face_layer] = int(self.assign)

        bmesh.update_edit_mesh(me)
        return utils.layer_face_count(bm, face_layer)

    def execute(self, context):
        ob = context.object
        nwo = ob.data.nwo
        item = nwo.face_props[nwo.face_props_active_index]
        item.face_count = self.edit_layer(ob.data, item.layer_name)
        if nwo.highlight:
            bpy.ops.nwo.face_layer_color_all(enable_highlight=nwo.highlight)

        context.area.tag_redraw()

        return {"FINISHED"}


class NWO_OT_FaceLayerSelect(bpy.types.Operator):
    bl_idname = "nwo.face_layer_select"
    bl_label = "Select"
    bl_options = {'UNDO'}

    select: bpy.props.BoolProperty(default=True)

    def select_by_layer(self, me, layer_name):
        bm = bmesh.from_edit_mesh(me)
        # get list of selected faces
        face_layer = bm.faces.layers.int.get(layer_name)
        if face_layer is None:
            face_layer = bm.faces.layers.int.new(layer_name)
        for face in bm.faces:
            if face[face_layer] == 1:
                face.select = self.select

        bmesh.update_edit_mesh(me)

    def execute(self, context):
        ob = context.object
        nwo = ob.data.nwo
        item = nwo.face_props[nwo.face_props_active_index]
        self.select_by_layer(ob.data, item.layer_name)
        return {"FINISHED"}


class NWO_OT_FaceLayerMove(bpy.types.Operator):
    bl_idname = "nwo.face_layer_move"
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
        face_layers = nwo.face_props
        active_index = nwo.face_props_active_index
        delta = {
            "DOWN": 1,
            "UP": -1,
        }[self.direction]

        to_index = (active_index + delta) % len(face_layers)

        face_layers.move(active_index, to_index)
        nwo.face_props_active_index = to_index

        return {"FINISHED"}


class NWO_OT_FaceLayerAddFaceMode(NWO_OT_FaceLayerAdd):
    """Adds a face property that will override face properties set in the mesh"""

    bl_idname = "nwo.face_layer_add_face_mode"

    options: bpy.props.EnumProperty(
        items=[
            ("_connected_geometry_face_mode_render_only", "Render Only", ""),
            (
                "_connected_geometry_face_mode_collision_only",
                "Collision Only",
                "",
            ),
            (
                "_connected_geometry_face_mode_sphere_collision_only",
                "Sphere Collision Only",
                "",
            ),
            (
                "_connected_geometry_face_mode_lightmap_only",
                "Lightmap Only",
                "",
            ),
            ("_connected_geometry_face_mode_breakable", "Breakable", ""),
        ]
    )

class NWO_OT_FaceLayerAddLightmap(NWO_OT_FaceLayerAdd):
    """Adds a face property that will override face properties set in the mesh"""

    bl_idname = "nwo.face_layer_add_lightmap"

    options: bpy.props.EnumProperty(
        items=[
            ("lightmap_additive_transparency", "Transparency", ""),
            ("lightmap_resolution_scale", "Resolution Scale", ""),
            ("lightmap_type", "Lightmap Type", ""),
            # ('lightmap_analytical_bounce_modifier', 'Analytical Light Bounce Modifier', ''),
            # ('lightmap_general_bounce_modifier', 'General Light Bounce Modifier', ''),
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
        ]
    )


class NWO_OT_FacePropRemove(bpy.types.Operator):
    bl_idname = "nwo.face_prop_remove"
    bl_label = "Remove"
    bl_description = 'Removes a face property'
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.data and context.object.type in VALID_MESHES and context.object.data.nwo.face_props_active_index > -1

    options: bpy.props.EnumProperty(
        items=[
            ("seam", "", ""),
            ("region", "", ""),
            ("face_global_material", "", ""),
            ("face_mode", "", ""),
            ("two_sided", "", ""),
            ("transparent", "", ""),
            ("draw_distance", "", ""),
            ("mesh_tessellation_density", "", ""),
            ("texcoord_usage", "", ""),
            ("ladder", "Ladder", ""),
            ("slip_surface", "", ""),
            ("breakable", "", ""),
            ("decal_offset", "", ""),
            ("no_shadow", "", ""),
            ("precise_position", "", ""),
            ("no_lightmap", "", ""),
            ("lightmap_only", "", ""),
            ("no_pvs", "", ""),
            ("lightmap_additive_transparency", "", ""),
            ("lightmap_resolution_scale", " ", ""),
            ("lightmap_type", "Lightmap Type", ""),
            ("lightmap_analytical_bounce_modifier", "", ""),
            ("lightmap_general_bounce_modifier", "", ""),
            ("lightmap_translucency_tint_color", "", ""),
            ("lightmap_lighting_from_both_sides", "", ""),
            ("emissive", "", ""),
        ],
    )

    def execute(self, context):
        nwo = context.object.data.nwo
        toggle_override(self.options, False, nwo.face_props[nwo.face_props_active_index])
        context.area.tag_redraw()
        return {"FINISHED"}


class NWO_OT_FacePropAdd(NWO_OT_FaceLayerAdd):
    bl_idname = "nwo.face_prop_add"

    new: bpy.props.BoolProperty(default=False)


class NWO_OT_FacePropAddFaceMode(NWO_OT_FaceLayerAddFaceMode):
    bl_idname = "nwo.face_prop_add_face_mode"

    new: bpy.props.BoolProperty(default=False)


class NWO_OT_FacePropAddLightmap(NWO_OT_FaceLayerAddLightmap):
    bl_idname = "nwo.face_prop_add_lightmap"

    new: bpy.props.BoolProperty(default=False)


def draw(self):
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.face_culling_set("BACK")

    matrix = bpy.context.region_data.perspective_matrix
    self.shader.uniform_float(
        "ModelViewProjectionMatrix", matrix @ self.ob.matrix_world
    )
    self.shader.uniform_float(
        "color", (self.color.r, self.color.g, self.color.b, self.alpha)
    )
    self.shader.bind()
    self.batch.draw(self.shader)

    gpu.state.blend_set("NONE")
    gpu.state.depth_test_set("NONE")
    gpu.state.face_culling_set("NONE")


class NWO_OT_FaceLayerColorAll(bpy.types.Operator):
    bl_idname = "nwo.face_layer_color_all"
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
                
        if self.enable_highlight:
            face_layers = me.nwo.face_props
            for index in range(len(face_layers)):
                bpy.ops.nwo.face_layer_color(layer_index=index,highlight=int_highlight)

        return {"FINISHED"}


class NWO_OT_FaceLayerColor(bpy.types.Operator):
    bl_idname = "nwo.face_layer_color"
    bl_label = "Highlight"
    bl_options = {'INTERNAL'}

    layer_index: bpy.props.IntProperty()
    highlight: bpy.props.IntProperty()

    def ensure_loops(self, bm):
        try:
            if self.loops is None:
                self.loops = bm.calc_loop_triangles()
            else:
                if len(self.loops):
                    loop_tris = self.loops[0]
                    if len(loop_tris):
                        loop = loop_tris[0]
                        loop.face
        except:
            self.loops = bm.calc_loop_triangles()

        return self.loops

    def shader_prep(self, context):
        self.shader = gpu.shader.from_builtin("UNIFORM_COLOR")

        bm = bmesh.from_edit_mesh(self.me)
        self.volume = bm.calc_volume()
        cm = bm.copy()
        vert_coords = [v.co for v in cm.verts]
        offset = 0.05 if context.scene.nwo.scale == 'max' else 0.005
        for f in cm.faces:
            displacement = f.normal * offset
            face_verts = f.verts

            for vert in face_verts:
                vert.co = vert_coords[vert.index] + displacement

        self.layer = cm.faces.layers.int.get(self.layer_name)
        self.verts = (
            [
                loop.vert.co.to_tuple()
                for loop_tris in self.ensure_loops(cm)
                for loop in loop_tris
                if loop_tris[0].face.hide is False and loop_tris[0].face[self.layer]
            ]
            if self.layer
            else []
        )

        if self.verts:
            self.batch = batch_for_shader(self.shader, "TRIS", {"pos": self.verts})

    def modal(self, context, event):
        edit_mode = context.mode == "EDIT_MESH"

        if edit_mode:
            bm = bmesh.from_edit_mesh(self.me)
            bm_v = bm.calc_volume()
            bm.free()
        else:
            bm_v = self.volume

        if (
            event.type in ("G", "S", "R", "E", "K", "B", "I", "V")  
            or event.value == "CLICK_DRAG"
        ):
            self.alpha = 0
        else:
            self.alpha = 0.25

        global int_highlight
        kill_highlight = (
            not edit_mode
            or self.highlight != int_highlight
            or self.layer is None
            or not self.me.nwo.highlight
            or not self.me.nwo.face_props
        )

        if kill_highlight or bm_v != self.volume:
            self.handler = bpy.types.SpaceView3D.draw_handler_remove(self.handler, "WINDOW")
            if kill_highlight:
                self.tag_redraw()
                return {"FINISHED"}
            else:
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.editmode_toggle()
                return {"CANCELLED"}

        return {"PASS_THROUGH"}
    
    def tag_redraw(self):
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if(area.type == 'VIEW_3D'):
                    area.tag_redraw()

    def execute(self, context):
        self.ob = context.object
        self.me = self.ob.data

        layer = self.me.nwo.face_props[self.layer_index]
        self.layer_name = layer.layer_name
        self.color = layer.layer_color
        self.alpha = 0
        self.batch = None

        self.shader_prep(context)

        if self.verts:
            self.handler = bpy.types.SpaceView3D.draw_handler_add(draw, (self,), "WINDOW", "POST_VIEW")
            context.window_manager.modal_handler_add(self)
            bpy.ops.object.editmode_toggle()
            bpy.ops.object.editmode_toggle()
            return {"RUNNING_MODAL"}

        return {"CANCELLED"}


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
        nwo.face_props[nwo.face_props_active_index].face_global_material = self.region
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
                layout.operator('nwo.apply_type_mesh_single', text='Bounding Box', icon_value=get_icon_id('streaming')).m_type = 'obb_volume'
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

# FACE LEVEL FACE PROPS

class NWO_UL_FaceMapProps(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            if item:
                layout.prop(item, "name", text="", emboss=False, icon_value=495)
            else:
                layout.label(text="", translate=False, icon_value=icon)
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)

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


# MESH LEVEL FACE PROPS


def toggle_active(context, option, bool_var):
    ob = context.object
    ob_nwo = ob.data.nwo

    match option:
        case "_connected_geometry_face_sides_one_sided_transparent":
            ob_nwo.face_sides_active = bool_var
            ob_nwo.face_sides_ui = (
                "_connected_geometry_face_sides_one_sided_transparent"
            )
        case "ladder":
            ob_nwo.ladder_active = bool_var
        case "slip_surface":
            ob_nwo.slip_surface_active = bool_var
        case "decal_offset":
            ob_nwo.decal_offset_active = bool_var
        case "no_shadow":
            ob_nwo.no_shadow_active = bool_var
        case "precise_position":
            ob_nwo.precise_position_active = bool_var
        case "no_lightmap":
            ob_nwo.no_lightmap_active = bool_var
        case "lightmap_only":
            ob_nwo.lightmap_only_active = bool_var
        case "no_pvs":
            ob_nwo.no_pvs_active = bool_var
        # lightmap
        case "lightmap_additive_transparency":
            ob_nwo.lightmap_additive_transparency_active = bool_var
        case "lightmap_resolution_scale":
            ob_nwo.lightmap_resolution_scale_active = bool_var
        case "lightmap_type":
            ob_nwo.lightmap_type_active = bool_var
        case "lightmap_analytical_bounce_modifier":
            ob_nwo.lightmap_analytical_bounce_modifier_active = bool_var
        case "lightmap_general_bounce_modifier":
            ob_nwo.lightmap_general_bounce_modifier_active = bool_var
        case "lightmap_translucency_tint_color":
            ob_nwo.lightmap_translucency_tint_color_active = bool_var
        case "lightmap_lighting_from_both_sides":
            ob_nwo.lightmap_lighting_from_both_sides_active = bool_var
        # material lighting
        case "emissive":
            ob_nwo.emissive_active = bool_var


class NWO_MT_MeshPropAddMenu(bpy.types.Menu):
    bl_label = "Add Mesh Property"
    bl_idname = "NWO_MT_MeshPropAdd"
    
    @classmethod
    def poll(cls, context):
        return context.object and utils.is_mesh(context.object)

    def draw(self, context):
        layout = self.layout
        nwo = context.object.nwo
        if utils.poll_ui(("scenario", "prefab")):
            # if nwo.mesh_type == "_connected_geometry_mesh_type_structure":
            #     layout.operator(
            #         "nwo.add_mesh_property", text="Sky"
            #     ).options = "_connected_geometry_face_type_sky"
            # if nwo.mesh_type in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure"):
            #     layout.operator(
            #         "nwo.add_mesh_property", text="Seam Sealer"
            #     ).options = "_connected_geometry_face_type_seam_sealer"
            if nwo.mesh_type in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_lightmap_only"):
                layout.operator(
                    "nwo.add_mesh_property", text="Emissive"
                ).options = "emissive"
                layout.operator_menu_enum(
                    "nwo.add_mesh_property_lightmap",
                    property="options",
                    text="Lightmap",
                )

class NWO_OT_MeshPropAdd(bpy.types.Operator):
    """Adds a face property that will override face properties set in the mesh"""

    bl_idname = "nwo.add_mesh_property"
    bl_label = "Add"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and utils.is_mesh(context.object)

    options: bpy.props.EnumProperty(
        items=[
            ("emissive", "Emissive", ""),
            ("_connected_geometry_face_type_sky", "Sky", ""),
            ("_connected_geometry_face_type_seam_sealer", "Seam Sealer", ""),
        ]
    )

    def execute(self, context):
        toggle_active(context, self.options, True)
        context.area.tag_redraw()
        return {"FINISHED"}


class NWO_OT_MeshPropRemove(bpy.types.Operator):
    """Removes a mesh property"""

    bl_idname = "nwo.remove_mesh_property"
    bl_label = "Remove"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object

    options: bpy.props.EnumProperty(
        items=[
            ("ladder", "Ladder", ""),
            ("slip_surface", "Slip Surface", ""),
            ("decal_offset", "Decal Offset", ""),
            ("group_transparents_by_plane", "Group Transparents by Plane", ""),
            ("no_shadow", "No Shadow", ""),
            ("precise_position", "Precise Position", ""),
            ("no_lightmap", "No Lightmap", ""),
            ("lightmap_only", "Lightmap Only", ""),
            ("no_pvs", "No PVS", ""),
            ("lightmap_additive_transparency", "Transparency", ""),
            ("lightmap_resolution_scale", "Resolution Scale", ""),
            ("lightmap_type", "Lightmap Type", ""),
            ("lightmap_translucency_tint_color", "Translucency Tint Color", ""),
            ("lightmap_lighting_from_both_sides", "Lighting from Both Sides", ""),
            ("emissive", "Emissive", ""),
        ]
    )

    def execute(self, context):
        toggle_active(context, self.options, False)
        context.area.tag_redraw()
        return {"FINISHED"}


class NWO_OT_MeshPropAddLightmap(NWO_OT_MeshPropAdd):
    bl_idname = "nwo.add_mesh_property_lightmap"
    bl_label = "Add"

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
        ]
    )

# LIST SYSTEMS
# ------------------------------------------------


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
    bl_label = "Collision Material List"
    bl_description = "Applies a global material to the selected object"

    def execute(self, context):
        context.object.data.nwo.face_global_material = self.region
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
        nwo = context.object.data.nwo
        if self.face_level:
            nwo.face_props[nwo.face_props_active_index].face_global_material = self.material
        else:
            nwo.face_global_material = self.material
        context.area.tag_redraw()
        return {"FINISHED"}
    
    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'material', text="Collision Material")

class NWO_OT_GlobalMaterialList(bpy.types.Operator):
    bl_idname = "nwo.global_material_list"
    bl_label = "Collision Material List"
    bl_description = "Applies a Collision Material to the selected object"
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
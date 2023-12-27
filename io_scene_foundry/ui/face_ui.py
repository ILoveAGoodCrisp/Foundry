# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

from ..utils.nwo_utils import (
    is_corinth,
    layer_face_count,
    random_color,
    true_region,
    poll_ui,
)
from .templates import NWO_Op
from bpy.props import EnumProperty, BoolProperty, StringProperty
import bpy
import bmesh
from uuid import uuid4
import gpu
from gpu_extras.batch import batch_for_shader

int_highlight = 0


class NWO_FaceLayerAddMenu(bpy.types.Menu):
    bl_label = "Add Face Property"
    bl_idname = "NWO_MT_FaceLayerAdd"

    def __init__(self):
        self.op_prefix = "nwo.face_layer_add"

    def draw(self, context):
        layout = self.layout
        ob = context.object
        nwo = ob.nwo
        h4 = is_corinth(context)
        if poll_ui(("MODEL", "SKY")):
            layout.operator(self.op_prefix, text="Region").options = "region"
        # if (
        #     poll_ui("SCENARIO")
        #     and nwo.mesh_type_ui == "_connected_geometry_mesh_type_default"
        # ):
        #     layout.operator(self.op_prefix, text="Seam").options = "seam"
        if (h4 and
            (nwo.mesh_type_ui == "_connected_geometry_mesh_type_collision"
            or nwo.mesh_type_ui == "_connected_geometry_mesh_type_physics"
            or nwo.mesh_type_ui == "_connected_geometry_mesh_type_default"
            or (nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure" and poll_ui(('SCENARIO', 'PREFAB')))
        ) or (not h4 and nwo.mesh_type_ui in ("_connected_geometry_mesh_type_physics", "_connected_geometry_mesh_type_collision"))):
            layout.operator(
                self.op_prefix, text="Collision Material"
            ).options = "face_global_material"
        if nwo.mesh_type_ui in (
            "_connected_geometry_mesh_type_default",
            "_connected_geometry_mesh_type_structure",
            "_connected_geometry_mesh_type_collision",
        ):
            layout.operator(self.op_prefix, text="Two Sided").options = "two_sided"
            if nwo.mesh_type_ui != '_connected_geometry_mesh_type_collision':
                layout.operator(self.op_prefix, text="Transparent").options = "transparent"
        if poll_ui(("MODEL", "SCENARIO", "PREFAB")):
            if nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_default",
                "_connected_geometry_mesh_type_structure",
            ):
                layout.operator(
                    self.op_prefix, text="Uncompressed"
                ).options = "precise_position"
                
            if poll_ui(("SCENARIO", "PREFAB")) and nwo.mesh_type_ui in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_structure', '_connected_geometry_mesh_type_collision'):
                if h4 and nwo.mesh_type_ui != '_connected_geometry_mesh_type_collision':
                    layout.operator(
                        self.op_prefix, text="No Lightmap"
                    ).options = "no_lightmap"
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
                if nwo.mesh_type_ui != '_connected_geometry_mesh_type_collision':
                    layout.operator(
                        self.op_prefix, text="Decal Offset"
                    ).options = "decal_offset"
                    layout.operator(
                        self.op_prefix, text="No Shadow"
                    ).options = "no_shadow"
            elif poll_ui(("MODEL")):
                if nwo.mesh_type_ui == '_connected_geometry_mesh_type_collision' and not h4:
                    layout.operator(
                        self.op_prefix, text="Ladder"
                    ).options = "ladder"
                    layout.operator(
                        self.op_prefix, text="Slip Surface"
                    ).options = "slip_surface"
                elif nwo.mesh_type_ui != '_connected_geometry_mesh_type_collision':
                    layout.operator(
                        self.op_prefix, text="Decal Offset"
                    ).options = "decal_offset"

        if poll_ui(("SCENARIO", "PREFAB")):
            if nwo.mesh_type_ui == "_connected_geometry_mesh_type_default":
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


class NWO_FacePropAddMenu(NWO_FaceLayerAddMenu):
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
                
class NWO_UpdateLayersFaceCount(bpy.types.Operator):
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
            face_layer.face_count = layer_face_count(bm, bm.faces.layers.int.get(face_layer.layer_name))
            
        return {"FINISHED"}



def toggle_override(context, option, bool_var):
    ob = context.object
    nwo = ob.data.nwo
    item = nwo.face_props[nwo.face_props_index]

    match option:
        case "region":
            item.region_name_override = bool_var
        case "two_sided":
            item.face_two_sided_override = bool_var
        case "transparent":
            item.face_transparent_override = bool_var
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
        case "face_draw_distance":
            item.face_draw_distance_override = bool_var
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


class NWO_EditMode(NWO_Op):
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


class NWO_FaceLayerAdd(NWO_Op):
    bl_idname = "nwo.face_layer_add"
    bl_label = "Add Face Layer"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == "MESH"

    new: BoolProperty(default=True)

    options: EnumProperty(
        default="region",
        items=[
            ("region", "Region", ""),
            ("emissive", "Emissive", ""),
            ("face_global_material", "Collision Material", ""),
            ("precise_position", "Precise Position", ""),
            ("two_sided", "Two Sided", ""),
            ("transparent", "Transparent", ""),
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
            ("no_pvs", "No Visibility Culling", ""),
        ],
    )

    fm_name: StringProperty()

    def add_face_layer(self, me, prefix):
        bm = bmesh.from_edit_mesh(me)
        face_layer = bm.faces.layers.int.new(f"{prefix}_{str(uuid4())}")
        # get list of selected faces
        for face in bm.faces:
            if face.select:
                face[face_layer] = 1

        bmesh.update_edit_mesh(me)
        return face_layer.name, layer_face_count(bm, face_layer)

    def execute(self, context):
        ob = context.object
        nwo = ob.data.nwo
        match self.options:
            case "seam":
                self.fm_name = f"seam {true_region(ob.nwo)}:"
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

        if self.new:
            layer_name, face_count = self.add_face_layer(ob.data, self.fm_name)
            bpy.ops.uilist.entry_add(
                list_path="object.data.nwo.face_props",
                active_index_path="object.data.nwo.face_props_index",
            )

        toggle_override(context, self.options, True)
        item = nwo.face_props[nwo.face_props_index]

        if self.new:
            item.name = self.fm_name
            item.layer_name = layer_name
            item.face_count = face_count
            item.layer_color = random_color()
            if nwo.highlight:
                bpy.ops.nwo.face_layer_color_all(enable_highlight=nwo.highlight)

        if self.options == "region":
            region = context.scene.nwo.regions_table[0].name
            item.name = 'region' + '::' + region
            item.region_name_ui = region
            
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


class NWO_FaceLayerRemove(NWO_Op):
    """Removes a face layer"""

    bl_idname = "nwo.face_layer_remove"
    bl_label = "Remove"
    bl_options = {"UNDO"}

    @classmethod
    def poll(self, context):
        ob = context.object
        if ob.type == "MESH":
            nwo = ob.data.nwo
            return nwo.face_props
        return False

    def remove_face_layer(self, me, layer_name):
        bm = bmesh.from_edit_mesh(me)
        # get list of selected faces
        try:
            bm.faces.layers.int.remove(bm.faces.layers.int.get(layer_name))
        except:
            pass

        bmesh.update_edit_mesh(me)

    def execute(self, context):
        ob = context.object
        nwo = ob.data.nwo
        item = nwo.face_props[nwo.face_props_index]
        self.remove_face_layer(ob.data, item.layer_name)
        nwo.face_props.remove(nwo.face_props_index)
        if nwo.face_props_index > len(nwo.face_props) - 1:
            nwo.face_props_index += -1
        if nwo.highlight:
            bpy.ops.nwo.face_layer_color_all(enable_highlight=nwo.highlight)

        context.area.tag_redraw()
        # gotta do this mess so undo states correctly register
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        bpy.ops.ed.undo_push()
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        return {"FINISHED"}


class NWO_FaceLayerAssign(NWO_Op):
    bl_idname = "nwo.face_layer_assign"
    bl_label = "Remove"

    assign: BoolProperty(default=True)

    def edit_layer(self, me, layer_name):
        bm = bmesh.from_edit_mesh(me)
        # get list of selected faces
        face_layer = bm.faces.layers.int.get(layer_name)
        for face in bm.faces:
            if face.select:
                face[face_layer] = int(self.assign)

        bmesh.update_edit_mesh(me)
        return layer_face_count(bm, face_layer)

    def execute(self, context):
        ob = context.object
        nwo = ob.data.nwo
        item = nwo.face_props[nwo.face_props_index]
        item.face_count = self.edit_layer(ob.data, item.layer_name)
        if nwo.highlight:
            bpy.ops.nwo.face_layer_color_all(enable_highlight=nwo.highlight)

        context.area.tag_redraw()

        return {"FINISHED"}


class NWO_FaceLayerSelect(NWO_Op):
    bl_idname = "nwo.face_layer_select"
    bl_label = "Select"

    select: BoolProperty(default=True)

    def select_by_layer(self, me, layer_name):
        bm = bmesh.from_edit_mesh(me)
        # get list of selected faces
        face_layer = bm.faces.layers.int.get(layer_name)
        for face in bm.faces:
            if face[face_layer] == 1:
                face.select = self.select

        bmesh.update_edit_mesh(me)

    def execute(self, context):
        ob = context.object
        nwo = ob.data.nwo
        item = nwo.face_props[nwo.face_props_index]
        self.select_by_layer(ob.data, item.layer_name)
        return {"FINISHED"}


class NWO_FaceLayerMove(NWO_Op):
    bl_idname = "nwo.face_layer_move"
    bl_label = "Move"

    direction: EnumProperty(
        name="Direction",
        items=(("UP", "UP", "UP"), ("DOWN", "DOWN", "DOWN")),
        default="UP",
    )

    @classmethod
    def poll(self, context):
        ob = context.object
        if ob.type == "MESH":
            nwo = ob.data.nwo
            return nwo.face_props
        return False

    def execute(self, context):
        ob = context.object
        nwo = ob.data.nwo
        face_layers = nwo.face_props
        active_index = nwo.face_props_index
        delta = {
            "DOWN": 1,
            "UP": -1,
        }[self.direction]

        to_index = (active_index + delta) % len(face_layers)

        face_layers.move(active_index, to_index)
        nwo.face_props_index = to_index

        return {"FINISHED"}


class NWO_FaceLayerAddFaceMode(NWO_FaceLayerAdd):
    """Adds a face property that will override face properties set in the mesh"""

    bl_idname = "nwo.face_layer_add_face_mode"

    options: EnumProperty(
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

class NWO_FaceLayerAddLightmap(NWO_FaceLayerAdd):
    """Adds a face property that will override face properties set in the mesh"""

    bl_idname = "nwo.face_layer_add_lightmap"

    options: EnumProperty(
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


class NWO_FacePropRemove(NWO_Op):
    bl_idname = "nwo.face_prop_remove"
    bl_label = "Remove"
    bl_description = 'Removes a face property'

    options: EnumProperty(
        items=[
            ("seam", "", ""),
            ("region", "", ""),
            ("face_global_material", "", ""),
            ("face_mode", "", ""),
            ("two_sided", "", ""),
            ("transparent", "", ""),
            ("texcoord_usage", "", ""),
            ("ladder", "Ladder", ""),
            ("slip_surface", "", ""),
            ("breakable", "", ""),
            ("decal_offset", "", ""),
            ("no_shadow", "", ""),
            ("precise_position", "", ""),
            ("no_lightmap", "", ""),
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
        toggle_override(context, self.options, False)
        context.area.tag_redraw()
        return {"FINISHED"}


class NWO_FacePropAdd(NWO_FaceLayerAdd):
    bl_idname = "nwo.face_prop_add"

    new: BoolProperty(default=False)


class NWO_FacePropAddFaceMode(NWO_FaceLayerAddFaceMode):
    bl_idname = "nwo.face_prop_add_face_mode"

    new: BoolProperty(default=False)


class NWO_FacePropAddLightmap(NWO_FaceLayerAddLightmap):
    bl_idname = "nwo.face_prop_add_lightmap"

    new: BoolProperty(default=False)


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


class NWO_FaceLayerColorAll(bpy.types.Operator):
    bl_idname = "nwo.face_layer_color_all"
    bl_label = "Highlight"

    enable_highlight: BoolProperty()

    def execute(self, context):
        ob = context.object
        me = ob.data
        me.nwo.highlight = self.enable_highlight

        if self.enable_highlight:
            global int_highlight
            if int_highlight < 1000:
                int_highlight += 1
            else:
                int_highlight = 0

            face_layers = me.nwo.face_props
            for index in range(len(face_layers)):
                bpy.ops.nwo.face_layer_color(
                    "INVOKE_DEFAULT",
                    layer_index=index,
                    highlight=int_highlight,
                )

        return {"FINISHED"}


class NWO_FaceLayerColor(bpy.types.Operator):
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

    def shader_prep(self):
        self.shader = gpu.shader.from_builtin("UNIFORM_COLOR")

        bm = bmesh.from_edit_mesh(self.me)
        self.volume = bm.calc_volume()
        cm = bm.copy()
        vert_coords = [v.co for v in cm.verts]
        offset = 0.05
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
            try:
                self.handler = bpy.types.SpaceView3D.draw_handler_remove(
                    self.handler, "WINDOW"
                )
            except:
                pass

            if kill_highlight:
                return {"CANCELLED"}
            else:
                bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
                bpy.ops.object.mode_set(mode="EDIT", toggle=False)
                return {"CANCELLED"}

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        self.ob = context.object
        self.me = self.ob.data

        layer = self.me.nwo.face_props[self.layer_index]
        self.layer_name = layer.layer_name
        self.color = layer.layer_color
        self.alpha = 0
        self.batch = None

        self.shader_prep()

        if self.verts:
            self.handler = bpy.types.SpaceView3D.draw_handler_add(
                draw, (self,), "WINDOW", "POST_VIEW"
            )
            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}

        return {"CANCELLED"}


class NWO_RegionListFace(bpy.types.Operator):
    bl_idname = "nwo.face_region_list"
    bl_label = "Region List"
    bl_description = "Applies a region to the selected face layer"

    def regions_items(self, context):
        items = []
        for r in context.scene.nwo.regions_table:
            items.append((r.name, r.name, ''))
        return items

    region: EnumProperty(
        name="Region",
        items=regions_items,
    )

    def execute(self, context):
        nwo = context.object.data.nwo
        nwo.face_props[nwo.face_props_index].region_name_ui = self.region
        return {"FINISHED"}


class NWO_GlobalMaterialRegionListFace(NWO_RegionListFace):
    bl_idname = "nwo.face_global_material_regions_list"
    bl_label = "Collision Material List"
    bl_description = "Applies a global material to the selected face layer"

    def execute(self, context):
        nwo = context.object.data.nwo
        nwo.face_props[nwo.face_props_index].face_global_material_ui = self.region
        return {"FINISHED"}


class NWO_GlobalMaterialMenuFace(bpy.types.Menu):
    bl_label = "Add Collision Material"
    bl_idname = "NWO_MT_AddGlobalMaterialFace"

    def draw(self, context):
        layout = self.layout
        if poll_ui(("MODEL", "SKY")):
            layout.operator_menu_enum(
                "nwo.face_global_material_regions_list",
                property="region",
                text="From Region",
            )

        if poll_ui(("SCENARIO", "PREFAB", "MODEL")):
            layout.operator(
                "nwo.global_material_globals",
                text="From Globals",
                icon="VIEWZOOM",
            ).face_level = True

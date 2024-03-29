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

from bpy.types import PropertyGroup
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    FloatVectorProperty,
)
from ..utils.nwo_utils import bpy_enum_seam, is_corinth, true_bsp


class NWO_FaceProperties_ListItems(PropertyGroup):
    layer_name: StringProperty()
    face_count: IntProperty(options=set())
    layer_color: FloatVectorProperty(
        subtype="COLOR_GAMMA",
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0,
        max=1,
        options=set(),
    )
    name: StringProperty()
    face_type_override: BoolProperty()
    face_mode_override: BoolProperty()
    face_two_sided_override: BoolProperty()
    face_transparent_override: BoolProperty()
    face_draw_distance_override: BoolProperty()
    texcoord_usage_override: BoolProperty()
    region_name_override: BoolProperty()
    is_pca_override: BoolProperty()
    face_global_material_override: BoolProperty()
    sky_permutation_index_override: BoolProperty()
    ladder_override: BoolProperty()
    slip_surface_override: BoolProperty()
    decal_offset_override: BoolProperty()
    group_transparents_by_plane_override: BoolProperty()
    no_shadow_override: BoolProperty()
    precise_position_override: BoolProperty()
    no_lightmap_override: BoolProperty()
    no_pvs_override: BoolProperty()
    # instances
    instanced_collision_override: BoolProperty()
    instanced_physics_override: BoolProperty()
    cookie_cutter_override: BoolProperty()
    # lightmap
    lightmap_additive_transparency_override: BoolProperty()
    lightmap_resolution_scale_override: BoolProperty()
    lightmap_type_override: BoolProperty()
    lightmap_analytical_bounce_modifier_override: BoolProperty()
    lightmap_general_bounce_modifier_override: BoolProperty()
    lightmap_translucency_tint_color_override: BoolProperty()
    lightmap_lighting_from_both_sides_override: BoolProperty()
    # material lighting
    emissive_override: BoolProperty()
    # seam
    seam_override: BoolProperty()

    # def seam_item(self, context):
    #     return [('seam', true_bsp(context.object.nwo), "Allows visisbility between connected BSPs. Requires a zone set to be set up in the scenario tag containing the connected BSPs", get_icon_id("seam_facing"), 0)]

    # seam : EnumProperty(
    #     name="Seam Facing BSP",
    #     options=set(),
    #     items=seam_item,
    #     )

    def scene_bsps(self, context):
        bsp_list = []
        for ob in context.scene.objects:
            bsp = true_bsp(ob.nwo)
            if bsp not in bsp_list and bsp != true_bsp(context.object.nwo):
                bsp_list.append(bsp)

        items = []
        for index, bsp in enumerate(bsp_list):
            items.append(bpy_enum_seam(bsp, index))

        return items

    seam_adjacent_bsp: StringProperty(
        name="Seam Backfacing BSP",
        description="The BSP that this seam has it's back to",
        options=set(),
    )

    face_type_ui: EnumProperty(
        name="Face Type",
        options=set(),
        description="Sets the face type for this mesh. Note that any override shaders will override the face type selected here for relevant materials",
        items=[
            (
                "_connected_geometry_face_type_seam_sealer",
                "Seam Sealer",
                "Used on faces that will not be seen by the player, however are required to make a mesh manifold or to properly block light.  Seam sealer faces use no lightmap space.  Can also be used on render only meshes",
            ),
            (
                "_connected_geometry_face_type_sky",
                "Sky",
                "Assigned faces will act as a window into the sky assigned to the level in the .scenario tag",
            ),
        ],
    )

    def face_mode_items(self, context):
        h4 = is_corinth(context)
        items = []
        items.append((
            "_connected_geometry_face_mode_render_only",
            "Render Only",
            "Faces set to render only",
        ))
        items.append((
            "_connected_geometry_face_mode_collision_only",
            "Collision Only",
            "Faces set to collision only",
        ))
        items.append((
            "_connected_geometry_face_mode_sphere_collision_only",
            "Sphere Collision Only",
            "Faces set to sphere collision only. Only objects with physics models can collide with these faces",
        ))
        items.append((
            "_connected_geometry_face_mode_shadow_only",
            "Shadow Only",
            "Faces set to only cast shadows",
        ))
        items.append((
            "_connected_geometry_face_mode_lightmap_only",
            "Lightmap Only",
            "Faces set to only be used during lightmapping. They will otherwise have no render / collision geometry",
        ))
        if not h4:
            items.append((
            "_connected_geometry_face_mode_breakable",
            "Breakable",
            "Faces set to be breakable",
            )),

        return items
    
    def get_face_mode_ui(self):
        max_int = 4
        if not is_corinth():
            max_int = 5
        if self.face_mode_ui_help > max_int:
            return 0
        return self.face_mode_ui_help

    def set_face_mode_ui(self, value):
        self["face_mode_ui"] = value

    def update_face_mode_ui(self, context):
        self.face_mode_ui_help = self["face_mode_ui"]

    face_mode_ui_help : IntProperty()
    face_mode_ui: EnumProperty(
        name="Face Mode",
        options=set(),
        description="Sets the face mode",
        items=face_mode_items,
        get=get_face_mode_ui,
        set=set_face_mode_ui,
        update=update_face_mode_ui,
    )

    face_sides_ui: EnumProperty(
        name="Face Sides",
        options=set(),
        description="Sets the face sides for this mesh",
        items=[
            (
                "_connected_geometry_face_sides_one_sided_transparent",
                "One Sided Transparent",
                "Faces set to only render on one side (the direction of face normals), but also render geometry behind them",
            ),
            (
                "_connected_geometry_face_sides_two_sided",
                "Two Sided",
                "Faces set to render on both sides",
            ),
            (
                "_connected_geometry_face_sides_two_sided_transparent",
                "Two Sided Transparent",
                "Faces set to render on both sides and are transparent",
            ),
            ("_connected_geometry_face_sides_mirror", "Mirror", "H4+ only"),
            (
                "_connected_geometry_face_sides_mirror_transparent",
                "Mirror Transparent",
                "H4+ only",
            ),
            ("_connected_geometry_face_sides_keep", "Keep", "H4+ only"),
            (
                "_connected_geometry_face_sides_keep_transparent",
                "Keep Transparent",
                "H4+ only",
            ),
        ],
    )

    face_two_sided_ui: BoolProperty(
        name="Two Sided",
        description="Render the backfacing normal of this mesh, or if this mesh is collision, prevent open edges being treated as such in game",
        options=set(),
    )

    face_transparent_ui: BoolProperty(
        name="Transparent",
        description="Game treats this mesh as being transparent. If you're using a shader/material which has transparency, set this flag",
        options=set(),
    )

    face_two_sided_type_ui: EnumProperty(
        name="Two Sided Policy",
        description="Set how the game should render the opposite side of mesh faces",
        options=set(),
        items=[
            ("two_sided", "Default", "No special properties"),
            ("mirror", "Mirror", "Mirror backside normals from the frontside"),
            ("keep", "Keep", "Keep the same normal on each face side"),
        ]
    )

    face_draw_distance_ui: EnumProperty(
        name="Face Draw Distance",
        options=set(),
        description="Controls the distance at which the assigned faces will stop rendering",
        default="_connected_geometry_face_draw_distance_normal",
        items=[
            ("_connected_geometry_face_draw_distance_normal", "Normal", ""),
            ("_connected_geometry_face_draw_distance_detail_mid", "Mid", ""),
            (
                "_connected_geometry_face_draw_distance_detail_close",
                "Close",
                "",
            ),
        ],
    )

    texcoord_usage_ui: EnumProperty(
        name="Texture Coordinate Usage",
        options=set(),
        description="",
        default="_connected_material_texcoord_usage_default",
        items=[
            ("_connected_material_texcoord_usage_default", "Default", ""),
            ("_connected_material_texcoord_usage_none", "None", ""),
            (
                "_connected_material_texcoord_usage_anisotropic",
                "Ansiotropic",
                "",
            ),
        ],
    )

    region_name_ui: StringProperty(
        name="Region",
        default="default",
        description="Define the name of the region these faces should be associated with",
    )

    face_global_material_ui: StringProperty(
        name="Collision Material",
        default="",
        description="Set the Collision Material of this mesh. If the Collision Material name matches a valid material defined in tags\globals\globals.globals then this mesh will automatically take the correct Collision Material response type, otherwise, the Collision Material override can be manually defined in the .model tag",
    )

    sky_permutation_index_ui: IntProperty(
        name="Sky Permutation Index",
        options=set(),
        description="The sky permutation index of the sky faces",
        min=0,
    )

    conveyor_ui: BoolProperty(  # UNSUPPORTED
        name="Conveyor",
        options=set(),
        description="Enables the conveyor property",
        default=True,
    )

    ladder_ui: BoolProperty(
        name="Ladder",
        options=set(),
        description="Makes faces climbable",
        default=True,
    )

    slip_surface_ui: BoolProperty(
        name="Slip Surface",
        options=set(),
        description="Assigned faces will be non traversable by the player. Used to ensure the player can not climb a surface regardless of slope angle",
        default=True,
    )

    decal_offset_ui: BoolProperty(
        name="Decal Offset",
        options=set(),
        description="Provides a Z bias to the faces that will not be overridden by the plane build.  If placing a face coplanar against another surface, this flag will prevent Z fighting",
        default=True,
    )

    group_transparents_by_plane_ui: BoolProperty(
        name="Group Transparents By Plane",
        options=set(),
        description="Determines if objects will sort based on center point or by plane.  Provides more accurate sorting of large alpha'd objects, but is very expensive",
        default=True,
    )

    no_shadow_ui: BoolProperty(
        name="No Shadow",
        options=set(),
        description="Prevents faces from casting shadows",
        default=True,
    )

    precise_position_ui: BoolProperty(
        name="Precise Position",
        options=set(),
        description="Provides more accurate render and collision geometry",
        default=True,
    )

    no_lightmap_ui: BoolProperty(
        name="Exclude From Lightmap",
        options=set(),
        description="",
        default=True,
    )

    no_pvs_ui: BoolProperty(
        name="Invisible To PVS",
        options=set(),
        description="",
        default=True,
    )

    # INSTANCED GEOMETRY ONLY

    instanced_collision: BoolProperty(
        name="Bullet Collision",
        default=True,
    )
    instanced_physics: BoolProperty(
        name="Player Collision",
        default=True,
    )

    cookie_cutter: BoolProperty(
        name="Cookie Cutter",
        default=True,
    )

    #########

    # LIGHTMAP

    lightmap_additive_transparency_ui: FloatVectorProperty(
        name="Additive Transparency",
        options=set(),
        description="Overrides the amount and color of light that will pass through the surface. Tint color will override the alpha blend settings in the shader.",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    lightmap_resolution_scale_ui: FloatProperty(
        name="Resolution Scale",
        options=set(),
        description="Determines how much texel space the faces will be given on the lightmap.  1 means less space for the faces, while 7 means more space for the faces. The relationships can be tweaked in the .scenario tag",
        default=3,
        min=0,
        max=7,
    )

    lightmap_photon_fidelity_ui: EnumProperty(
        name="Photon Fidelity",
        options=set(),
        description="",
        default="_connected_material_lightmap_photon_fidelity_normal",
        items=[
            (
                "_connected_material_lightmap_photon_fidelity_normal",
                "Normal",
                "",
            ),
            (
                "_connected_material_lightmap_photon_fidelity_medium",
                "Medium",
                "",
            ),
            ("_connected_material_lightmap_photon_fidelity_high", "High", ""),
            ("_connected_material_lightmap_photon_fidelity_none", "None", ""),
        ],
    )

    # Lightmap_Chart_Group: IntProperty(
    #     name="Lightmap Chart Group",
    #     options=set(),
    #     description="",
    #     default=3,
    #     min=1,
    # )

    lightmap_type_ui: EnumProperty(
        name="Lightmap Type",
        options=set(),
        description="Sets how this should be lit while lightmapping",
        default="_connected_material_lightmap_type_per_pixel",
        items=[
            ("_connected_material_lightmap_type_per_pixel", "Per Pixel", ""),
            ("_connected_material_lightmap_type_per_vertex", "Per Vetex", ""),
        ],
    )

    lightmap_analytical_bounce_modifier_ui: FloatProperty(
        name="Lightmap Analytical Bounce Modifier",
        options=set(),
        description="0 will bounce no energy.  1 will bounce full energy.  Any value greater than 1 will exaggerate the amount of bounced light.  Affects 1st bounce only",
        default=1,
        soft_max=1,
        min=0,
        subtype="FACTOR",
    )

    lightmap_general_bounce_modifier_ui: FloatProperty(
        name="Lightmap General Bounce Modifier",
        options=set(),
        description="0 will bounce no energy.  1 will bounce full energy.  Any value greater than 1 will exaggerate the amount of bounced light.  Affects 1st bounce only",
        default=1,
        soft_max=1,
        min=0,
        subtype="FACTOR",
    )

    lightmap_translucency_tint_color_ui: FloatVectorProperty(
        name="Translucency Tint Color",
        options=set(),
        description="",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    lightmap_lighting_from_both_sides_ui: BoolProperty(
        name="Lighting From Both Sides",
        options=set(),
        description="",
        default=True,
    )

    # MATERIAL LIGHTING

    material_lighting_attenuation_cutoff_ui: FloatProperty(
        name="Attenuation Cutoff",
        options=set(),
        description="Determines how far light travels before it stops",
        min=0,
        default=200,
    )

    material_lighting_attenuation_falloff_ui: FloatProperty(
        name="Attenuation Falloff",
        options=set(),
        description="For use on emissive surfaces. The distance in game units at which the light intensity will begin to fall off until reaching zero at the attenuation cutoff value",
        min=0,
        default=100,
    )

    material_lighting_emissive_focus_ui: FloatProperty(
        name="Emissive Focus",
        options=set(),
        description="Controls the spread of the light emitting from this surface. 0 will emit light in a 180 degrees hemisphere from each point, 1 will emit light nearly perpendicular to the surface",
        min=0,
        max=1,
        subtype="FACTOR",
    )

    material_lighting_emissive_color_ui: FloatVectorProperty(
        name="Emissive Color",
        options=set(),
        description="The RGB value of the emitted light",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    material_lighting_emissive_per_unit_ui: BoolProperty(
        name="Emissive Per Unit",
        options=set(),
        description="When an emissive surface is scaled, determines if the amount of emitted light should be spread out across the surface or increased/decreased to keep a regular amount of light emission per unit area",
        default=False,
    )

    material_lighting_emissive_power_ui: FloatProperty(
        name="Emissive Power",
        options=set(),
        description="The intensity of the emissive surface",
        min=0,
        default=2,
    )

    material_lighting_emissive_quality_ui: FloatProperty(
        name="Emissive Quality",
        options=set(),
        description="Controls the quality of the shadows cast by a complex occluder. For instance, a light casting shadows of tree branches on a wall would require a higher quality to get smooth shadows",
        default=1,
        min=0,
    )

    material_lighting_use_shader_gel_ui: BoolProperty(
        name="Use Shader Gel",
        options=set(),
        description="",
        default=False,
    )

    material_lighting_bounce_ratio_ui: FloatProperty(
        name="Lighting Bounce Ratio",
        options=set(),
        description="0 will bounce no energy. 1 will bounce full energy. Any value greater than 1 will exaggerate the amount of bounced light. Affects 1st bounce only",
        default=1,
        min=0,
    )

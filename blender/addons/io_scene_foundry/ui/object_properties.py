# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
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

import random
import uuid
from .face_properties import NWO_FaceProperties_ListItems
from bpy.props import (
    IntProperty,
    BoolProperty,
    EnumProperty,
    FloatProperty,
    StringProperty,
    PointerProperty,
    FloatVectorProperty,
    CollectionProperty,
)
from bpy.types import PropertyGroup
import bpy
from ..icons import get_icon_id
from ..utils.nwo_utils import (
    calc_light_energy,
    clean_tag_path,
    dot_partition,
    calc_light_intensity,
    get_exclude_collections,
    get_object_type,
    get_prop_from_collection,
    is_corinth,
    is_mesh,
    nwo_enum,
    poll_ui,
    wu,
)

# def get_default_mesh_type():
#     appdata = os.getenv('APPDATA')
#     foundry_folder = os.path.join(appdata, "Foundry")
#     mesh_file = os.path.join(foundry_folder, 'mesh_default.txt')
#     if os.path.exists(mesh_file):
#         with open(mesh_file, 'r') as f:
#             value = f.read()
#         return value

#     return '_connected_geometry_mesh_type_default'

# MESH PROPS
# ----------------------------------------------------------


class NWO_MeshPropertiesGroup(PropertyGroup):
    proxy_collision: PointerProperty(type=bpy.types.Object)
    proxy_physics: PointerProperty(type=bpy.types.Object)
    proxy_cookie_cutter: PointerProperty(type=bpy.types.Object)
    
    mesh_type_ui: StringProperty(
        name="Mesh Type",
        default='_connected_geometry_mesh_type_default',
        options=set(),
    )

    face_props: CollectionProperty(
        type=NWO_FaceProperties_ListItems, override={"USE_INSERTION"}
    )

    face_props_index: IntProperty(
        name="Index for Face Property",
        default=0,
        min=0,
    )

    highlight: BoolProperty(
        options=set(),
        name="Highlight",
    )
    
    face_global_material_ui: StringProperty(
        name="Collision Material",
        default="",
        description="Set the Collision Material of this mesh. If the Collision Material name matches a valid material defined in tags\globals\globals.globals then this mesh will automatically take the correct Collision Material response type, otherwise, the Collision Material override can be manually defined in the .model tag",
    )

    mesh_face: EnumProperty(
        name="Mesh | Face",
        items=[
            ("mesh", "MOP", "Mesh Object Properties"),
            ("face", "FLOP", "Face Level Object Properties"),
        ],
        options=set(),
    )

    def update_face_type_ui(self, context):
        self.face_type_active = True
    
    def poop_collision_type_items(self, context):
        items = []
        items.append(("_connected_geometry_poop_collision_type_default", "Full", "Collision mesh that interacts with the physics objects and with projectiles"))
        items.append(("_connected_geometry_poop_collision_type_invisible_wall", "Sphere Collision", "Collision mesh that interacts with the physics objects only"))
        items.append(("_connected_geometry_poop_collision_type_play_collision", "Player Collision", "Collision mesh that affects physics objects and physical projectiles, such as grenades"))
        items.append(("_connected_geometry_poop_collision_type_bullet_collision", "Bullet Collision", "Collision mesh that only interacts with simple projectiles, such as bullets"))
        
        return items
        
    poop_collision_type_ui: EnumProperty(
        name="Collision Type",
        options=set(),
        description="",
        items=poop_collision_type_items,
    )
    
    render_only_ui: BoolProperty(
        name="Render Only",
        description="Mesh has no collision",
        options=set(),
    )
    
    sphere_collision_only_ui: BoolProperty(
        name="Sphere Collision Only",
        description="Only physics objects collide with this mesh. Projectiles will pass through it",
        options=set(),
    )
    
    breakable_ui: BoolProperty(
        name="Breakable",
        description="Geometry can be broken",
        options=set(),
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

    ladder_ui: BoolProperty(
        name="Ladder",
        options=set(),
        description="Makes faces climbable",
    )

    slip_surface_ui: BoolProperty(
        name="Slip Surface",
        options=set(),
        description="Makes faces slippery for units",
    )


    decal_offset_ui: BoolProperty(
        name="Decal Offset",
        options=set(),
        description="Enable to offset these faces so that they appear to be layered on top of another face",
        default=False,
    )
    
    no_shadow_ui: BoolProperty(
        name="No Shadow",
        options=set(),
        description="Prevents faces from casting shadows",
    )

    precise_position_ui: BoolProperty(
        name="Precise Position",
        options=set(),
        description="Disables compression of vertices during export, resulting in more accurate (and expensive) meshes in game. Only use this when you need to",
    )

    no_lightmap_ui: BoolProperty(
        name="Exclude From Lightmap",
        options=set(),
        description="Exclude mesh from lightmapping",
    )

    no_pvs_ui: BoolProperty(
        name="Invisible To PVS",
        options=set(),
        description="Mesh is unaffected by Potential Visbility Sets - the games render culling system",
    )
    
    def update_lightmap_additive_transparency_ui(self, context):
        self.lightmap_additive_transparency_active = True

    lightmap_additive_transparency_active: BoolProperty()
    lightmap_additive_transparency_ui: FloatVectorProperty(
        name="lightmap Additive Transparency",
        options=set(),
        description="Overrides the amount and color of light that will pass through the surface. Tint color will override the alpha blend settings in the shader",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        update=update_lightmap_additive_transparency_ui,
    )

    def update_lightmap_ignore_default_resolution_scale_ui(self, context):
        self.lightmap_ignore_default_resolution_scale_active = True

    lightmap_ignore_default_resolution_scale_active: BoolProperty()
    lightmap_ignore_default_resolution_scale_ui: BoolProperty(
        name="Lightmap Resolution Scale",
        options=set(),
        description="",
        default=False,
        update=update_lightmap_ignore_default_resolution_scale_ui,
    )

    def update_lightmap_resolution_scale_ui(self, context):
        self.lightmap_resolution_scale_active = True

    lightmap_resolution_scale_active: BoolProperty()
    lightmap_resolution_scale_ui: FloatProperty(
        name="Resolution Scale",
        options=set(),
        default=3.0,
        min=0.0,
        max=7.0,
        description="Determines how much texel space the faces will be given on the lightmap.  1 means less space for the faces, while 7 means more space for the faces. The relationships can be tweaked in the .scenario tag",
        update=update_lightmap_resolution_scale_ui,
    )

    def update_lightmap_photon_fidelity_ui(self, context):
        self.lightmap_photon_fidelity_active = True

    lightmap_photon_fidelity_active: BoolProperty()
    lightmap_photon_fidelity_ui: EnumProperty(
        name="Photon Fidelity",
        options=set(),
        update=update_lightmap_photon_fidelity_ui,
        description="H4+ only",
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

    def update_lightmap_type_ui(self, context):
        self.lightmap_type_active = True

    lightmap_type_active: BoolProperty()
    lightmap_type_ui: EnumProperty(
        name="Lightmap Type",
        options=set(),
        update=update_lightmap_type_ui,
        description="Sets how this should be lit while lightmapping",
        default="_connected_material_lightmap_type_per_pixel",
        items=[
            ("_connected_material_lightmap_type_per_pixel", "Per Pixel", ""),
            ("_connected_material_lightmap_type_per_vertex", "Per Vertex", ""),
        ],
    )

    lightmap_transparency_override_ui: BoolProperty(
        name="Lightmap Transparency Override",
        options=set(),
        description="",
        default=False,
    )

    def update_lightmap_analytical_bounce_modifier_ui(self, context):
        self.lightmap_analytical_bounce_modifier_active = True

    lightmap_analytical_bounce_modifier_active: BoolProperty()
    lightmap_analytical_bounce_modifier_ui: FloatProperty(
        name="Lightmap Analytical Bounce Modifier",
        options=set(),
        description="",
        default=1,
        update=update_lightmap_analytical_bounce_modifier_ui,
    )

    def update_lightmap_general_bounce_modifier_ui(self, context):
        self.lightmap_general_bounce_modifier_active = True

    lightmap_general_bounce_modifier_active: BoolProperty()
    lightmap_general_bounce_modifier_ui: FloatProperty(
        name="Lightmap General Bounce Modifier",
        options=set(),
        description="",
        default=1,
        update=update_lightmap_general_bounce_modifier_ui,
    )

    def update_lightmap_translucency_tint_color_ui(self, context):
        self.lightmap_translucency_tint_color_active = True

    lightmap_translucency_tint_color_active: BoolProperty()
    lightmap_translucency_tint_color_ui: FloatVectorProperty(
        name="Lightmap Translucency Tint Color",
        options=set(),
        description="",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        update=update_lightmap_translucency_tint_color_ui,
    )

    def update_lightmap_lighting_from_both_sides_ui(self, context):
        self.lightmap_lighting_from_both_sides_active = True

    lightmap_lighting_from_both_sides_active: BoolProperty()
    lightmap_lighting_from_both_sides_ui: BoolProperty(
        name="Lightmap Lighting From Both Sides",
        options=set(),
        description="",
        default=False,
        update=update_lightmap_lighting_from_both_sides_ui,
    )

    # MATERIAL LIGHTING PROPERTIES

    # def update_emissive(self, context):
    #     self.emissive_active = True

    emissive_active: BoolProperty()
    material_lighting_attenuation_active: BoolProperty()
    
            
    def update_lighting_attenuation_falloff(self, context):
        if self.material_lighting_attenuation_falloff_ui > self.material_lighting_attenuation_cutoff_ui:
            self.material_lighting_attenuation_cutoff_ui = self.material_lighting_attenuation_falloff_ui
            
    def update_lighting_attenuation_cutoff(self, context):
        if self.material_lighting_attenuation_cutoff_ui < self.material_lighting_attenuation_falloff_ui:
            self.material_lighting_attenuation_falloff_ui = self.material_lighting_attenuation_cutoff_ui
    
    material_lighting_attenuation_cutoff_ui: FloatProperty(
        name="Material Lighting Attenuation Cutoff",
        options=set(),
        description="Determines how far light travels before it stops",
        min=0,
        default=0,
        update=update_lighting_attenuation_cutoff,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    lighting_attenuation_enabled: BoolProperty(
        name="Use Attenuation",
        options=set(),
        description="Enable / Disable use of attenuation",
        default=True,
    )

    material_lighting_attenuation_falloff_ui: FloatProperty(
        name="Material Lighting Attenuation Falloff",
        options=set(),
        description="Determines how far light travels before its power begins to falloff",
        min=0,
        default=0,
        update=update_lighting_attenuation_falloff,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    material_lighting_emissive_focus_active: BoolProperty()
    material_lighting_emissive_focus_ui: FloatProperty(
        name="Material Lighting Emissive Focus",
        options=set(),
        description="Controls the spread of the light emitting from this surface. 0 will emit light in a 180 degrees hemisphere from each point, 1 will emit light nearly perpendicular to the surface",
        min=0,
        max=1,
        subtype="FACTOR",
    )

    material_lighting_emissive_color_active: BoolProperty()
    material_lighting_emissive_color_ui: FloatVectorProperty(
        name="Material Lighting Emissive Color",
        options=set(),
        description="The RGB value of the emitted light",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    material_lighting_emissive_per_unit_active: BoolProperty()
    material_lighting_emissive_per_unit_ui: BoolProperty(
        name="Material Lighting Emissive Per Unit",
        options=set(),
        description="When an emissive surface is scaled, determines if the amount of emitted light should be spread out across the surface or increased/decreased to keep a regular amount of light emission per unit area",
        default=False,
    )

    material_lighting_emissive_power_active: BoolProperty()
    material_lighting_emissive_power_ui: FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="The intensity of the emissive surface",
        min=0,
        default=10,
        subtype='POWER',
        unit='POWER',
        # update=update_emissive,
    )

    material_lighting_emissive_quality_active: BoolProperty()
    material_lighting_emissive_quality_ui: FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="Controls the quality of the shadows cast by a complex occluder. For instance, a light casting shadows of tree branches on a wall would require a higher quality to get smooth shadows",
        default=1,
        min=0,
    )

    material_lighting_use_shader_gel_active: BoolProperty()
    material_lighting_use_shader_gel_ui: BoolProperty(
        name="Material Lighting Use Shader Gel",
        options=set(),
        description="",
        default=False,
    )

    material_lighting_bounce_ratio_active: BoolProperty()
    material_lighting_bounce_ratio_ui: FloatProperty(
        name="Material Lighting Bounce Ratio",
        options=set(),
        description="0 will bounce no energy. 1 will bounce full energy. Any value greater than 1 will exaggerate the amount of bounced light. Affects 1st bounce only",
        default=1,
        min=0,
    )

# MARKER PERM PROPERTIES
# ----------------------------------------------------------
class NWO_MarkerPermutationItems(PropertyGroup):
    name: StringProperty(name="Permutation")

# OBJECT PROPERTIES
# ----------------------------------------------------------
class NWO_ObjectPropertiesGroup(PropertyGroup):
    ### PROXY
    proxy_parent: PointerProperty(type=bpy.types.Mesh)
    proxy_type : StringProperty()
    #### MARKER PERM
    marker_permutations: CollectionProperty(
        type=NWO_MarkerPermutationItems,
    )

    marker_permutations_index: IntProperty(
        name="Index for Animation Event",
        default=0,
        min=0,
    )

    marker_permutation_type : EnumProperty(
        name="Include/Exclude",
        description="Toggle whether this marker should be included in, or excluded from the below list of permutations. If this is set to include and no permutations are defined, this property will be ignored at export",
        items=[
            ("exclude", "Exclude", ""),
            ("include", "Include", ""),
        ],
        options=set(),
    )
    
    # MAIN
    proxy_instance: BoolProperty(
        name="Proxy Instance",
        description="Duplicates this structure mesh as instanced geometry at export",
        options=set(),
    )

    # def items_object_type_ui(self, context):
    #     """Function to handle context for object enum lists"""
    #     ob = context.object
    #     items = []

    #     # context: any light object
    #     if ob.type == "LIGHT":
    #         items.append(
    #             (
    #                 "_connected_geometry_object_type_light",
    #                 "Light",
    #                 "Light",
    #                 get_icon_id("light_cone"),
    #                 0,
    #             )
    #         )

    #     # context: any 3D object type i.e. a blender mesh or an object that can convert to mesh
    #     elif mesh_object(ob):
    #         items.append(
    #             (
    #                 "_connected_geometry_object_type_mesh",
    #                 "Mesh",
    #                 "Mesh",
    #                 get_icon_id("mesh"),
    #                 0,
    #             )
    #         )
    #         items.append(
    #             (
    #                 "_connected_geometry_object_type_marker",
    #                 "Marker",
    #                 "Marker",
    #                 get_icon_id("marker"),
    #                 1,
    #             )
    #         )
    #         items.append(
    #             (
    #                 "_connected_geometry_object_type_frame",
    #                 "Frame",
    #                 "Frame",
    #                 get_icon_id("frame"),
    #                 2,
    #             )
    #         )

    #     # context: any empty object
    #     else:
    #         items.append(
    #             (
    #                 "_connected_geometry_object_type_marker",
    #                 "Marker",
    #                 "Marker",
    #                 get_icon_id("marker"),
    #                 0,
    #             )
    #         )
    #         items.append(
    #             (
    #                 "_connected_geometry_object_type_frame",
    #                 "Frame",
    #                 "Frame",
    #                 get_icon_id("frame"),
    #                 1,
    #             )
    #         )

    #     return items

    # def get_object_type_ui(self):
    #     max_int = 2
    #     try:
    #         ob = bpy.context.object
    #         if ob.type == "EMPTY":
    #             max_int = 1
    #         if self.object_type_ui_help > max_int:
    #             return 0
    #         return self.object_type_ui_help
    #     except:
    #         return self.object_type_ui_help

    # def set_object_type_ui(self, value):
    #     self["object_type_ui"] = value

    # def update_object_type_ui(self, context):
    #     self.object_type_ui_help = self["object_type_ui"]

    # object_type_ui: StringProperty(
    #     name="Object Type",
    #     # items=items_object_type_ui,
    #     # update=update_object_type_ui,
    #     # get=get_object_type_ui,
    #     # set=set_object_type_ui,
    # )

    # object_type_ui_help: IntProperty()

    #########################################################################################################################
    # MESH TYPE UI ####################################################################################################
    #########################################################################################################################

    def items_mesh_type_ui(self, context):
        """Function to handle context for mesh enum lists"""
        h4 = is_corinth()
        index = -1
        items = []

        if poll_ui("DECORATOR SET"):
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_decorator",
                    "Decorator",
                    "Decorator mesh type. Supports up to 4 level of detail variants",
                    "decorator",
                    index,
                )
            )
        elif poll_ui(("MODEL", "SKY", "PARTICLE MODEL")):
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_render",
                    "Render",
                    "Render only geometry",
                    "render_geometry",
                    index,
                )
            )
            index += 1
            if poll_ui("MODEL"):
                items.append(
                    nwo_enum(
                        "_connected_geometry_mesh_type_collision",
                        "Collision",
                        "Collision only geometry. Bullets always collide with this mesh. If this mesh is static (cannot move) and does not have a physics model, the collision model will also interact with physics objects such as the player",
                        "collider",
                        index,
                    )
                )
                index += 1
                items.append(
                    nwo_enum(
                        "_connected_geometry_mesh_type_physics",
                        "Physics",
                        "Physics only geometry. Uses havok physics to interact with static and dynamic objects",
                        "physics",
                        index,
                    )
                )
                # if not h4: NOTE removing these for now until I figure out how they work
                #     items.append(('_connected_geometry_mesh_type_object_instance', 'Flair', 'Instanced mesh for models. Can be instanced across mutliple permutations', get_icon_id("flair"), 3))
        elif poll_ui("SCENARIO"):
            if h4:
                descrip = "Defines the bounds of the BSP. Is always sky mesh and therefore has no render or collision geometry. Use the proxy instance option to add render/collision geometry"
            else:
                descrip = "Defines the bounds of the BSP. By default acts as render, collision and physics geometry"
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_structure",
                    "Structure",
                    descrip,
                    "structure",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_poop",
                    "Instance",
                    "Geometry capable of cutting through structure mesh. Can be instanced. Provides render, collision, and physics",
                    "instance",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_poop_collision",
                    "Collision",
                    "Non rendered geometry which provides collision only",
                    "collider",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_seam",
                    "Seam",
                    "Allows visibility and traversal between two or more bsps. Requires zone sets to be set up in the scenario tag",
                    "seam",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_portal",
                    "Portal",
                    "Planes that cut through structure geometry to define clusters. Used for defining visiblity between different clusters",
                    "portal",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_water_surface",
                    "Water Surface",
                    "Plane which can cut through geometry to define a water surface",
                    "water",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_soft_ceiling",
                    "Soft Ceiling",
                    "Soft barrier that blocks the player and player camera",
                    "soft_ceiling",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_soft_kill",
                    "Soft Kill",
                    "Defines a region where the player will be killed... softly",
                    "soft_kill",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_slip_surface",
                    "Slip Surface",
                    "Defines a region in which surfaces become slippery",
                    "slip_surface",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_water_physics_volume",
                    "Water Physics",
                    "Defines a region where water physics should apply. Material effects will play when projectiles strike this mesh. Underwater fog atmosphere will be used when the player is inside the volume (this appears broken in H4+)",
                    "water_physics",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_poop_rain_blocker",
                    "Rain Blocker",
                    "Blocks rain from rendering in the region this volume occupies",
                    "rain_blocker",
                    index,
                )
            )
            if h4:
                index += 1
                items.append(
                    nwo_enum(
                        "_connected_geometry_mesh_type_lightmap_exclude",
                        "Lightmap Exclusion Volume",
                        "Defines a region that should not be lightmapped",
                        "lightmap_exclude",
                        index,
                    )
                )   
                index += 1
                items.append(
                    nwo_enum(
                        "_connected_geometry_mesh_type_streaming",
                        "Streaming Volume",
                        "Defines the region in a zone set that should be used when generating a streamingzoneset tag. By default the full space inside a zone set should be used when generating the streaming zone set. This is useful for performance if you have textures in areas of the map the player will not get close to",
                        "streaming",
                        index,
                    )
                )   
            else:
                index += 1
                items.append(
                    nwo_enum(
                        "_connected_geometry_mesh_type_poop_vertical_rain_sheet",
                        "Rain Sheet",
                        "A plane which blocks all rain particles that hit it. Regions under this plane will not render rain",
                        "rain_sheet",
                        index,
                    )
                )
                index += 1
                items.append(
                    nwo_enum(
                        "_connected_geometry_mesh_type_cookie_cutter",
                        "Cookie Cutter",
                        "Cuts out the region this volume defines from the ai navigation mesh. Helpful in cases that you have ai pathing issues in your map",
                        "cookie_cutter",
                        index,
                    )
                )
                index += 1
                items.append(
                    nwo_enum(
                        "_connected_geometry_mesh_type_planar_fog_volume",
                        "Fog Plane",
                        "Defines an area in a cluster which renders fog defined in the scenario tag",
                        "fog",
                        index,
                    )
                )

        elif poll_ui("PREFAB"):
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_poop",
                    "Instance",
                    "Geometry capable of cutting through structure mesh. Can be instanced. Provides render, collision, and physics",
                    "instance",
                    index,
                )
            )
            index += 1
            items.append(
                nwo_enum(
                    "_connected_geometry_mesh_type_poop_collision",
                    "Collision",
                    "Non rendered geometry which provides collision only",
                    "collider",
                    index,
                )
            )
            # NOTE cookie cutters for H4 will need support through managedblam
            # items.append(
            #     nwo_enum(
            #         "_connected_geometry_mesh_type_cookie_cutter",
            #         "Cookie Cutter",
            #         "Cuts out the region this volume defines from the ai navigation mesh. Helpful in cases that you have ai pathing issues in your map",
            #         "cookie_cutter",
            #         2,
            #     )
            #)

        return items
    
    def get_mesh_type_ui(self):
        if not is_mesh(self.id_data):
            return '_connected_geometry_mesh_type_none'
        
        return self.id_data.data.nwo.mesh_type_ui

    mesh_type_ui: StringProperty(
        name="Mesh Type",
        default='_connected_geometry_mesh_type_default',
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_mesh_type_ui,
    )


    def items_marker_type_ui(self, context):
        """Function to handle context for marker enum lists"""
        h4 = is_corinth()
        items = []

        if poll_ui(("MODEL", "SKY")):
            items.append(
                (
                    "_connected_geometry_marker_type_model",
                    "Model Marker",
                    "Default marker type. Can be used as an attachment point for objects and effects",
                    get_icon_id("marker"),
                    0,
                )
            )
            items.append(
                (
                    "_connected_geometry_marker_type_effects",
                    "Effects",
                    'Marker type which automatically gets "fx_" prepended to the marker name at export',
                    get_icon_id("effects"),
                    1,
                )
            )
            if poll_ui("MODEL"):
                items.append(
                    (
                        "_connected_geometry_marker_type_garbage",
                        "Garbage",
                        "Marker for creating effects with velocity. Typically used for model damage sections",
                        get_icon_id("garbage"),
                        2,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_hint",
                        "Hint",
                        "This marker tells AI how to interact with parts of the model",
                        get_icon_id("hint"),
                        3,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_pathfinding_sphere",
                        "Pathfinding Sphere",
                        "Informs AI about how to path around this object. The sphere defines a region that AI should not enter",
                        get_icon_id("pathfinding_sphere"),
                        4,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_physics_constraint",
                        "Physics Constraint",
                        "Used for creating hinge and socket like contraints for objects. Allows object to have parts which react physically. For example creating a door which can be pushed open by the player, or a bipeds ragdoll",
                        get_icon_id("physics_constraint"),
                        5,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_target",
                        "Target",
                        "Used to specify an area on the model AI should target. Also used for checking whether a player is aiming at a target or not. Target properties are specified in the model tag",
                        get_icon_id("target"),
                        6,
                    )
                )
                if h4:
                    items.append(
                        (
                            "_connected_geometry_marker_type_airprobe",
                            "Airprobe",
                            "Airprobes store a representation of scenario lighting at their origins. Objects close to this airprobe will take its lighting values as their own. Helpful if an object is not being lit correctly in the scenario",
                            get_icon_id("airprobe"),
                            7,
                        )
                    )
        elif poll_ui("SCENARIO"):
            items.append(
                (
                    "_connected_geometry_marker_type_model",
                    "Structure Marker",
                    "Default marker type. Can be used as an attachment point for objects in Sapien",
                    get_icon_id("marker"),
                    0,
                )
            )
            tag_ext = dot_partition(self.marker_game_instance_tag_name_ui, True)
            match tag_ext:
                case "crate":
                    name = "Crate Tag"
                    icon = "crate"
                case "scenery":
                    name = "Scenery Tag"
                    icon = "scenery"
                case "effect_scenery":
                    name = "Effect Scenery Tag"
                    icon = "effect_scenery"
                case "device_control":
                    name = "Device Control Tag"
                    icon = "device_control"
                case "device_machine":
                    name = "Device Machine Tag"
                    icon = "device_machine"
                case "device_terminal":
                    name = "Device Terminal Tag"
                    icon = "device_terminal"
                case "device_dispenser":
                    name = "Device Dispenser Tag"
                    icon = "device_dispenser"
                case "biped":
                    name = "Biped Tag"
                    icon = "biped"
                case "creature":
                    name = "Creature Tag"
                    icon = "creature"
                case "giant":
                    name = "Giant Tag"
                    icon = "giant"
                case "vehicle":
                    name = "Vehicle Tag"
                    icon = "vehicle"
                case "weapon":
                    name = "Weapon Tag"
                    icon = "weapon"
                case "equipment":
                    name = "Equipment Tag"
                    icon = "equipment"
                case "prefab":
                    name = "Prefab Tag"
                    icon = "prefab"
                case "light":
                    name = "Light Tag"
                    icon = "light_cone"
                case "cheap_light":
                    name = "Cheap Light Tag"
                    icon = "light_cone"
                case "leaf":
                    name = "Leaf Tag"
                    icon = "decorator"
                case "decorator_set":
                    name = "Decorator Set Tag"
                    icon = "decorator"
                case _:
                    name = "Game Tag"
                    icon = "game_object"

            items.append(
                (
                    "_connected_geometry_marker_type_game_instance",
                    name,
                    "Creates the specified tag at this point in the scenario",
                    get_icon_id(icon),
                    1,
                )
            )

            if h4:
                items.append(
                    (
                        "_connected_geometry_marker_type_envfx",
                        "Environment Effect",
                        "Marker which loops the specified effect",
                        get_icon_id("environment_effect"),
                        2,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_lightCone",
                        "Light Cone",
                        "Creates a light cone with the parameters defined",
                        get_icon_id("light_cone"),
                        3,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_airprobe",
                        "Airprobe",
                        "Airprobes store a representation of scenario lighting at their origins. Objects close to this airprobe will take its lighting values as their own. Helpful if an object is not being lit correctly in the scenario",
                        get_icon_id("airprobe"),
                        4,
                    )
                )

        return items

    #########################################################################################################################
    # MARKER TYPE UI ####################################################################################################
    #########################################################################################################################

    def get_marker_type_ui(self):
        max_int = 0
        if poll_ui("MODEL"):
            if is_corinth():
                max_int = 7
            else:
                max_int = 6
        elif poll_ui("SCENARIO"):
            max_int = 4
            if not is_corinth():
                max_int = 1
        if self.marker_type_ui_help > max_int:
            return 0
        return self.marker_type_ui_help

    def set_marker_type_ui(self, value):
        self["marker_type_ui"] = value

    def update_marker_type_ui(self, context):
        self.marker_type_ui_help = self["marker_type_ui"]

    marker_type_ui: StringProperty(
        name="Marker Type",
        options=set(),
        default='_connected_geometry_marker_type_model',
        # items=items_marker_type_ui,
        # update=update_marker_type_ui,
        # get=get_marker_type_ui,
        # set=set_marker_type_ui,
    )

    marker_type_ui_help: IntProperty()

    export_this: BoolProperty(
        name="Export",
        default=True,
        description="Controls whether this object is exported or not",
        options=set(),
    )
    
    def get_exportable(self):
        if not self.export_this:
            return False
        ob = self.id_data
        if get_object_type(ob) == '_connected_geometry_object_type_none':
            return False
        if not ob.users_collection:
            return False
        
        exclude_collections = get_exclude_collections()
        exclude_collections_with_this_ob = [c for c in ob.users_collection if c in exclude_collections]
        if exclude_collections_with_this_ob:
            return False
        
        return True
    
    exportable: BoolProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_exportable,
    )
    
    # def get_export_type(self):
    #     ob = self.id_data
    #     nwo = ob.nwo
    #     if not nwo.export_this:
    #         return 'no_export_this'
    #     elif 
    
    # export_type: EnumProperty(get=get_export_type,
    #     items=[
    #         ('yes', '', ''),
    #         ('no_export_this', '', ''),
    #         ('no_exclude_collection', '', ''),
    #         ('no_invalid_object_type', '', ''),
    #     ]
    #     options={'HIDDEN' ,'SKIP_SAVe'}
    # )

    # OBJECT LEVEL PROPERTIES

    seam_back_ui: StringProperty(
        name="Seam Back Facing BSP",
        default="default",
        description="The BSP that the normals of this seam are facing away from",
    )

    def mesh_primitive_type_items(self, context):
        items = []
        items.append(("_connected_geometry_primitive_type_none", "None", "None", 0))
        items.append(("_connected_geometry_primitive_type_box", "Box", "Box", 1))
        items.append(("_connected_geometry_primitive_type_pill", "Pill", "Pill", 2))
        items.append(
            (
                "_connected_geometry_primitive_type_sphere",
                "Sphere",
                "Sphere",
                3,
            )
        )

        return items

    mesh_primitive_type_ui: EnumProperty(
        name="Mesh Primitive Type",
        options=set(),
        description="Select the primtive type of this mesh",
        items=mesh_primitive_type_items,
    )

    mesh_tessellation_density_ui: EnumProperty(
        name="Mesh Tessellation Density",
        options=set(),
        description="Select the tesselation density you want applied to this mesh",
        default="_connected_geometry_mesh_tessellation_density_none",
        items=[
            ("_connected_geometry_mesh_tessellation_density_none", "None", ""),
            (
                "_connected_geometry_mesh_tessellation_density_4x",
                "4x",
                "4 times",
            ),
            (
                "_connected_geometry_mesh_tessellation_density_9x",
                "9x",
                "9 times",
            ),
            (
                "_connected_geometry_mesh_tessellation_density_36x",
                "36x",
                "36 times",
            ),
        ],
    )

    poop_lighting_items = [
        (
            "_connected_geometry_poop_lighting_default",
            "Automatic",
            "Sets the lighting policy automatically",
        ),
        (
            "_connected_geometry_poop_lighting_per_pixel",
            "Per Pixel",
            "Sets the lighting policy to per pixel. Can be forced on with the prefix: '%?'",
        ),
        (
            "_connected_geometry_poop_lighting_per_vertex",
            "Per Vertex",
            "Sets the lighting policy to per vertex. Can be forced on with the prefix: '%!'",
        ),
        (
            "_connected_geometry_poop_lighting_single_probe",
            "Single Probe",
            "Sets the lighting policy to single probe. Can be forced on with the prefix: '%>'",
        ),
        (
            "_connected_geometry_poop_lighting_per_vertex_ao",
            "Per Vertex AO",
            "H4+ only. Sets the lighting policy to per vertex ambient occlusion.",
        ),
    ]

    # POOP PROPERTIES
    poop_lighting_ui: EnumProperty(
        name="Lighting Policy",
        options=set(),
        description="Sets the lighting policy for this instanced geometry",
        default="_connected_geometry_poop_lighting_per_pixel",
        items=poop_lighting_items,
    )

    poop_lightmap_resolution_scale_ui: FloatProperty(  # H4+ only NOTE not exposing this directly in UI. Instead using the mesh lightmap res prop
        name="Lightmap Resolution Scale",
        options=set(),
        description="Sets lightmap resolutions scale for this instance",
        default=3.0,
        min=0.0,
        max=7.0,
    )

    poop_pathfinding_items = [
        (
            "_connected_poop_instance_pathfinding_policy_cutout",
            "Cutout",
            "Sets the pathfinding policy to cutout. AI will be able to pathfind around this mesh, but not on it.",
        ),
        (
            "_connected_poop_instance_pathfinding_policy_none",
            "None",
            "Sets the pathfinding policy to none. This mesh will be ignored during pathfinding generation. Can be forced on with the prefix: '%-'",
        ),
        (
            "_connected_poop_instance_pathfinding_policy_static",
            "Static",
            "Sets the pathfinding policy to static. AI will be able to pathfind around and on this mesh. Can be forced on with the prefix: '%+'",
        ),
    ]

    poop_pathfinding_ui: EnumProperty(
        name="Instanced Geometry Pathfinding",
        options=set(),
        description="Sets the pathfinding policy for this instanced geometry",
        default="_connected_poop_instance_pathfinding_policy_cutout",
        items=poop_pathfinding_items,
    )

    poop_imposter_policy_ui: EnumProperty(
        name="Instanced Geometry Imposter Policy",
        options=set(),
        description="Sets the imposter policy for this instanced geometry",
        default="_connected_poop_instance_imposter_policy_never",
        items=[
            (
                "_connected_poop_instance_imposter_policy_polygon_default",
                "Polygon Default",
                "",
            ),
            (
                "_connected_poop_instance_imposter_policy_polygon_high",
                "Polygon High",
                "",
            ),
            (
                "_connected_poop_instance_imposter_policy_card_default",
                "Card Default",
                "",
            ),
            (
                "_connected_poop_instance_imposter_policy_card_high",
                "Card High",
                "",
            ),
            ("_connected_poop_instance_imposter_policy_never", "Never", ""),
        ],
    )

    poop_imposter_brightness_ui: FloatProperty(  # h4+
        name="Imposter Brightness",
        options=set(),
        description="Sets the brightness of the imposter variant of this instance",
        default=0.0,
        min=0.0,
    )

    poop_imposter_transition_distance_ui: FloatProperty(
        name="Instanced Geometry Imposter Transition Distance",
        options=set(),
        description="The distance at which the instanced geometry transitions to its imposter variant",
        default=50,
    )

    poop_imposter_transition_distance_auto: BoolProperty(
        name="Instanced Geometry Imposter Transition Automatic",
        options=set(),
        description="Enable to let the engine set the imposter transition distance by object size",
        default=True,
    )

    poop_streaming_priority_ui: EnumProperty(  # h4+
        name="Streaming Priority",
        options=set(),
        description="Sets the streaming priority for this instance",
        default="_connected_geometry_poop_streamingpriority_default",
        items=[
            (
                "_connected_geometry_poop_streamingpriority_default",
                "Default",
                "",
            ),
            (
                "_connected_geometry_poop_streamingpriority_higher",
                "Higher",
                "",
            ),
            (
                "_connected_geometry_poop_streamingpriority_highest",
                "Highest",
                "",
            ),
        ],
    )

    # Poop_Imposter_Fade_Range_Start: IntProperty(
    #     name="Instanced Geometry Fade Start",
    #     options=set(),
    #     description="Start to fade in this instanced geometry when its bounding sphere is more than or equal to X pixels on the screen",
    #     default=36,
    #     subtype='PIXEL',
    # )

    # Poop_Imposter_Fade_Range_End: IntProperty(
    #     name="Instanced Geometry Fade End",
    #     options=set(),
    #     description="Renders this instanced geometry fully when its bounding sphere is more than or equal to X pixels on the screen",
    #     default=30,
    #     subtype='PIXEL',
    # )

    # Poop_Decomposition_Hulls: FloatProperty(
    #     name="Instanced Geometry Decomposition Hulls",
    #     options=set(),
    #     description="",
    #     default= 4294967295,
    # )

    # Poop_Predominant_Shader_Name: StringProperty(
    #     name="Instanced Geometry Predominant Shader Name",
    #     description="I have no idea what this does, but we'll write whatever you put here into the json file. The path should be relative and contain the shader extension (e.g. shader_relative_path\shader_name.shader)",
    #     maxlen=1024,
    # )

    reach_poop_collision : BoolProperty() # INTERNAL

    poop_chops_portals_ui: BoolProperty(
        name="Chops Portals",
        options=set(),
        description="Instanced geometry set to chop portals",
        default=False,
    )

    poop_does_not_block_aoe_ui: BoolProperty(
        name="Does Not Block AOE",
        options=set(),
        description="Instanced geometry set to not block area of effect forces",
        default=False,
    )

    poop_excluded_from_lightprobe_ui: BoolProperty(
        name="Excluded From Lightprobe",
        options=set(),
        description="Sets this instanced geometry to be exlcuded from any lightprobes",
        default=False,
    )

    poop_decal_spacing_ui: BoolProperty(
        name="Decal Spacing",
        options=set(),
        description="Instanced geometry set to have decal spacing (like decal_offset)",
        default=False,
    )

    poop_precise_geometry_ui: BoolProperty(  # Implicit when precise position set
        name="Precise Geometry",
        options=set(),
        description="Instanced geometry set to not have its geometry altered in the BSP pass",
        default=False,
    )

    poop_remove_from_shadow_geometry_ui: BoolProperty(  # H4+
        name="Remove From Shadow Geo",
        options=set(),
        description="",
        default=False,
    )

    poop_disallow_lighting_samples_ui: BoolProperty(  # H4+
        name="Disallow Lighting Samples",
        options=set(),
        description="",
        default=False,
    )

    poop_rain_occluder_ui: BoolProperty(  # Implicit
        name="Rain Occluder",
        options=set(),
        description="",
        default=False,
    )

    poop_cinematic_properties_ui: EnumProperty(  # h4+
        name="Cinematic Properties",
        options=set(),
        description="Sets whether the instance should render only in cinematics, only outside of cinematics, or in both environments",
        default="_connected_geometry_poop_cinema_default",
        items=[
            (
                "_connected_geometry_poop_cinema_default",
                "Default",
                "Include both in cinematics and outside of them",
            ),
            (
                "_connected_geometry_poop_cinema_only",
                "Cinematic Only",
                "Only render in cinematics",
            ),
            (
                "_connected_geometry_poop_cinema_exclude",
                "Exclude From Cinematics",
                "Do not render in cinematics",
            ),
        ],
    )

    # poop light channel flags. Not included for now

    # portal PROPERTIES
    portal_type_ui: EnumProperty(
        name="Portal Type",
        options=set(),
        description="Sets the type of portal this mesh should be",
        default="_connected_geometry_portal_type_two_way",
        items=[
            (
                "_connected_geometry_portal_type_no_way",
                "No Way",
                "Sets the portal to block all visibility",
            ),
            (
                "_connected_geometry_portal_type_one_way",
                "One Way",
                "Sets the portal to block visibility from one direction",
            ),
            (
                "_connected_geometry_portal_type_two_way",
                "Two Way",
                "Sets the portal to have visiblity from both sides",
            ),
        ],
    )

    portal_ai_deafening_ui: BoolProperty(
        name="AI Deafening",
        options=set(),
        description="Stops AI hearing through this portal",
        default=False,
    )

    portal_blocks_sounds_ui: BoolProperty(
        name="Blocks Sounds",
        options=set(),
        description="Stops sound from travelling past this portal",
        default=False,
    )

    portal_is_door_ui: BoolProperty(
        name="Is Door",
        options=set(),
        description="Portal visibility is attached to a device machine state",
        default=False,
    )

    # DECORATOR PROPERTIES
    decorator_lod_ui: EnumProperty(
        name="Decorator Level of Detail",
        options=set(),
        description="Level of detail of this object. The game will switch to this LOD at the approriate range",
        items=[
            ("high", "High", ""),
            ("medium", "Medium", ""),
            ("low", "Low", ""),
            ("very_low", "Very Low", ""),
        ]
    )

    # WATER VOLUME PROPERTIES
    water_volume_depth_ui: FloatProperty(  # this something which can probably be automated?
        name="Water Volume Depth",
        options=set(),
        description="Set the depth of this water volume mesh",
        default=20,
    )
    water_volume_flow_direction_ui: FloatProperty(  # this something which can probably be automated?
        name="Water Volume Flow Direction",
        options=set(),
        description="Set the flow direction of this water volume mesh. 0 is forward on the X axis",
        subtype='ANGLE'
    )

    water_volume_flow_velocity_ui: FloatProperty(
        name="Water Volume Flow Velocity",
        options=set(),
        description="Set the flow velocity of this water volume mesh",
        default=1,
    )

    water_volume_fog_color_ui: FloatVectorProperty(
        name="Water Volume Fog Color",
        options=set(),
        description="Set the fog color of this water volume mesh",
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    water_volume_fog_murkiness_ui: FloatProperty(
        name="Water Volume Fog Murkiness",
        options=set(),
        description="Set the fog murkiness of this water volume mesh",
        default=0.5,
        subtype="FACTOR",
        min=0.0,
        max=1.0,
    )

    def fog_clean_tag_path(self, context):
        self["fog_appearance_tag_ui"] = clean_tag_path(
            self["fog_appearance_tag_ui"]
        ).strip('"')

    fog_appearance_tag_ui: StringProperty(
        name="Fog Appearance Tag",
        description="Name of the tag defining the fog volumes appearance",
        update=fog_clean_tag_path,
    )

    fog_volume_depth_ui: FloatProperty(
        name="Fog Volume Depth",
        options=set(),
        description="Set the depth of the fog volume",
        default=20,
    )

    marker_uses_regions: BoolProperty(
        name="Marker All Regions",
        options=set(),
        description="Associate this object with a specific region rather than all",
        default=False,
    )
    
    def get_marker_model_group(self):
        stripped_name = dot_partition(self.id_data.name).strip("#_?$-")
        if self.marker_type_ui == '_connected_geometry_marker_type_effects':
            if not stripped_name.startswith('fx_'):
                return "fx_" + stripped_name
        elif self.marker_type_ui == '_connected_geometry_marker_type_garbage':
            if not stripped_name.startswith('garbage_'):
                return "garbage_" + stripped_name
                
        return stripped_name
    
    marker_model_group: StringProperty(
        name="Marker Group",
        description="The group this marker is assigned to. Defined by the Blender object name, ignoring any characters after the last period (if any) and legacy object prefix/suffixes [#_?$-]",
        get=get_marker_model_group,
    )

    def game_instance_clean_tag_path(self, context):
        self["marker_game_instance_tag_name_ui"] = clean_tag_path(
            self["marker_game_instance_tag_name_ui"]
        ).strip('"')

    marker_game_instance_tag_name_ui: StringProperty(
        name="Marker Game Instance Tag",
        description="Define the name of the marker game instance tag",
        update=game_instance_clean_tag_path,
    )

    marker_game_instance_tag_variant_name_ui: StringProperty(
        name="Marker Game Instance Tag Variant",
        description="Define the name of the marker game instance tag variant",
    )

    marker_game_instance_run_scripts_ui: BoolProperty(
        name="Always Run Scripts",
        options=set(),
        description="Tells this game instance object to always run scripts if it has any",
        default=True,
    )

    marker_hint_length_ui: FloatProperty(
        name="Hint Length",
        options=set(),
        description="",
        default=0.0,
        min=0.0,
    )

    marker_hint_type: EnumProperty(
        name="Type",
        options=set(),
        description="",
        default="bunker",
        items=[
            ("bunker", "Bunker", ""),
            ("corner", "Corner", ""),
            ("vault", "Vault", ""),
            ("mount", "Mount", ""),
            ("hoist", "Hoist", ""),
        ],
    )

    marker_hint_side: EnumProperty(
        name="Side",
        options=set(),
        description="",
        default="right",
        items=[
            ("right", "Right", ""),
            ("left", "Left", ""),
        ],
    )

    marker_hint_height: EnumProperty(
        name="Height",
        options=set(),
        description="",
        default="step",
        items=[
            ("step", "Step", ""),
            ("crouch", "Crouch", ""),
            ("stand", "Stand", ""),
        ],
    )

    marker_sphere_radius_ui: FloatProperty(
        name="Sphere Radius",
        options=set(),
        description="Manually define the sphere radius for this marker. Alternatively, create a marker out of a mesh to have this radius set based on mesh dimensions",
        default=0.0,
        min=0.0,
    )

    marker_velocity_ui: FloatVectorProperty(
        name="Marker Velocity",
        options=set(),
        description="",
        subtype="VELOCITY",
    )

    marker_pathfinding_sphere_vehicle_ui: BoolProperty(
        name="Vehicle Only Pathfinding Sphere",
        options=set(),
        description="This pathfinding sphere only affects vehicles",
    )

    pathfinding_sphere_remains_when_open_ui: BoolProperty(
        name="Pathfinding Sphere Remains When Open",
        options=set(),
        description="Pathfinding sphere remains even when a machine is open",
    )

    pathfinding_sphere_with_sectors_ui: BoolProperty(
        name="Pathfinding Sphere With Sectors",
        options=set(),
        description="Not sure",
    )
    
    def poll_physics_constraint_target(self, object):
        return object.type == 'ARMATURE' or object.nwo.mesh_type_ui == '_connected_geometry_mesh_type_physics'

    physics_constraint_parent_ui: PointerProperty(
        name="Physics Constraint Parent",
        description="Enter the name of the object that is this marker's parent",
        type=bpy.types.Object,
        poll=poll_physics_constraint_target,
    )

    physics_constraint_parent_bone_ui: StringProperty(
        name="Physics Constraint Parent Bone",
        description="Enter the name of the bone that is this marker's parent",
    )

    physics_constraint_child_ui: PointerProperty(
        name="Physics Constraint Child",
        description="Enter the name of the object that is this marker's child",
        type=bpy.types.Object,
        poll=poll_physics_constraint_target,
    )

    physics_constraint_child_bone_ui: StringProperty(
        name="Physics Constraint Child Bone",
        description="Enter the name of the bone that is this marker's child",
    )

    physics_constraint_type_ui: EnumProperty(
        name="Constraint Type",
        options=set(),
        description="Select the physics constraint type",
        default="_connected_geometry_marker_type_physics_hinge_constraint",
        items=[
            (
                "_connected_geometry_marker_type_physics_hinge_constraint",
                "Hinge",
                "",
            ),
            (
                "_connected_geometry_marker_type_physics_socket_constraint",
                "Socket",
                "",
            ),
        ],
    )

    physics_constraint_uses_limits_ui: BoolProperty(
        name="Physics Constraint Uses Limits",
        options=set(),
        description="Set whether the limits of this physics constraint should be constrained or not",
    )

    hinge_constraint_minimum_ui: FloatProperty(
        name="Hinge Constraint Minimum",
        options=set(),
        description="Set the minimum rotation of a physics hinge",
        default=-180,
        min=-180,
        max=180,
    )

    hinge_constraint_maximum_ui: FloatProperty(
        name="Hinge Constraint Maximum",
        options=set(),
        description="Set the maximum rotation of a physics hinge",
        default=180,
        min=-180,
        max=180,
    )

    cone_angle_ui: FloatProperty(
        name="Cone Angle",
        options=set(),
        description="Set the cone angle",
        default=90,
        min=0,
        max=180,
    )

    plane_constraint_minimum_ui: FloatProperty(
        name="Plane Constraint Minimum",
        options=set(),
        description="Set the minimum rotation of a physics plane",
        default=-90,
        min=-90,
        max=0,
    )

    plane_constraint_maximum_ui: FloatProperty(
        name="Plane Constraint Maximum",
        options=set(),
        description="Set the maximum rotation of a physics plane",
        default=90,
        min=-0,
        max=90,
    )

    twist_constraint_start_ui: FloatProperty(
        name="Twist Constraint Minimum",
        options=set(),
        description="Set the starting angle of a twist constraint",
        default=-180,
        min=-180,
        max=180,
    )

    twist_constraint_end_ui: FloatProperty(
        name="Twist Constraint Maximum",
        options=set(),
        description="Set the ending angle of a twist constraint",
        default=180,
        min=-180,
        max=180,
    )

    def effect_clean_tag_path(self, context):
        self["marker_looping_effect_ui"] = clean_tag_path(
            self["marker_looping_effect_ui"]
        ).strip('"')

    marker_looping_effect_ui: StringProperty(
        name="Effect Path",
        description="Tag path to an effect",
        update=effect_clean_tag_path,
    )

    def light_cone_clean_tag_path(self, context):
        self["marker_light_cone_tag_ui"] = clean_tag_path(
            self["marker_light_cone_tag_ui"]
        ).strip('"')

    marker_light_cone_tag_ui: StringProperty(
        name="Light Cone Tag Path",
        description="Tag path to a light cone",
        update=light_cone_clean_tag_path,
    )

    marker_light_cone_color_ui: FloatVectorProperty(
        name="Light Cone Color",
        options=set(),
        description="",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    marker_light_cone_alpha_ui: FloatProperty(
        name="Light Cone Alpha",
        options=set(),
        description="",
        default=1.0,
        subtype="FACTOR",
        min=0.0,
        max=1.0,
    )

    marker_light_cone_width_ui: FloatProperty(
        name="Light Cone Width",
        options=set(),
        description="",
        default=5,
        min=0,
    )

    marker_light_cone_length_ui: FloatProperty(
        name="Light Cone Length",
        options=set(),
        description="",
        default=10,
        min=0,
    )

    marker_light_cone_intensity_ui: FloatProperty(
        name="Light Cone Intensity",
        options=set(),
        description="",
        default=1,
        min=0,
    )

    def light_cone_curve_clean_tag_path(self, context):
        self["marker_light_cone_curve_ui"] = clean_tag_path(
            self["marker_light_cone_curve_ui"]
        ).strip('"')

    marker_light_cone_curve_ui: StringProperty(
        name="Light Cone Curve Tag Path",
        description="",
        update=light_cone_curve_clean_tag_path,
    )

    def get_region_name_ui(self):
        scene_nwo = bpy.context.scene.nwo
        regions = scene_nwo.regions_table
        name = self.get("region_name_ui", "")
        if not regions:
            return "default"
        region_names = [r.name for r in regions]
        old_region_names = [r.old for r in regions]
        if name not in region_names and name not in old_region_names:
            name = scene_nwo.regions_table[0].name
        self['region_name_ui'] = name
        return name

    def set_region_name_ui(self, value):
        self['region_name_ui'] = value

    region_name_ui: StringProperty(
        name="Face Region",
        description="Define the name of the region these faces should be associated with",
        get=get_region_name_ui,
        set=set_region_name_ui,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_region_from_collection(self):
        region = get_prop_from_collection(self.id_data, 'region')
        return region

    region_name_locked_ui: StringProperty(
        name="Face Region",
        description="Define the region for this mesh",
        get=get_region_from_collection,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_permutation_name_ui(self):
        scene_nwo = bpy.context.scene.nwo
        permutations = scene_nwo.permutations_table
        name = self.get("permutation_name_ui", "")
        if not permutations:
            return "default"
        permutation_names = [p.name for p in permutations]
        old_permutation_names = [p.old for p in permutations]
        if name not in permutation_names and name not in old_permutation_names:
            name = scene_nwo.permutations_table[0].name
        self['permutation_name_ui'] = name
        return name

    def set_permutation_name_ui(self, value):
        self['permutation_name_ui'] = value

    permutation_name_ui: StringProperty(
        name="Permutation",
        default="default",
        description="Define the permutation of this object. Permutations get exported to seperate files in scenario exports, or in model exports if the mesh type is one of render/collision/physics",
        get=get_permutation_name_ui,
        set=set_permutation_name_ui,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_permutation_from_collection(self):
        permutation = get_prop_from_collection(self.id_data, 'permutation')
        return permutation

    permutation_name_locked_ui: StringProperty(
        name="Permutation",
        description="Define the permutation of this object. Leave blank for default",
        get=get_permutation_from_collection,
        override={'LIBRARY_OVERRIDABLE'},
    )

    is_pca_ui: BoolProperty(
        name="Frame PCA",
        options=set(),
        description="",
        default=False,
    )
    
    # GETTER PROPS
    def get_object_id(self):
        current_id = self.get('object_id', 0)
        if current_id:
            return current_id
        
        rnd = random.Random()
        id = str(uuid.UUID(int=rnd.getrandbits(128)))
        self['object_id'] = id
        return id
    
    ObjectID: StringProperty(
        get=get_object_id,
    )

    # EXPORT ONLY PROPS
    # --------------------------------------------------------
    object_type: StringProperty()
    mesh_type: StringProperty()
    marker_type: StringProperty()

    # OBJECT LEVEL
    # ---------------------------------
    permutation_name: StringProperty()
    is_pca: StringProperty()

    # BOUNDARY SURFACE
    boundary_surface_type: StringProperty()

    # POOP
    poop_lighting: StringProperty()
    poop_lightmap_resolution_scale: StringProperty()
    poop_pathfinding: StringProperty()
    poop_imposter_policy: StringProperty()
    poop_imposter_brightness: StringProperty()
    poop_imposter_transition_distance: StringProperty()
    poop_streaming_priority: StringProperty()
    poop_render_only: StringProperty()
    poop_chops_portals: StringProperty()
    poop_does_not_block_aoe: StringProperty()
    poop_excluded_from_lightprobe: StringProperty()
    poop_decal_spacing: StringProperty()
    poop_remove_from_shadow_geometry: StringProperty()
    poop_disallow_lighting_samples: StringProperty()
    poop_rain_occluder: StringProperty()
    poop_cinematic_properties: StringProperty()
    poop_collision_type: StringProperty()

    # PORTAL
    portal_type: StringProperty()
    portal_ai_deafening: StringProperty()
    portal_blocks_sounds: StringProperty()
    portal_is_door: StringProperty()

    # WATER SURFACE
    mesh_tessellation_density: StringProperty()

    # PHYSICS
    mesh_primitive_type: StringProperty()

    # DECORATOR
    decorator_lod: StringProperty()

    # SEAM
    seam_associated_bsp: StringProperty()

    # WATER VOLUME
    water_volume_depth: StringProperty()
    water_volume_flow_direction: StringProperty()
    water_volume_flow_velocity: StringProperty()
    water_volume_fog_color: StringProperty()
    water_volume_fog_murkiness: StringProperty()

    # FOG
    fog_appearance_tag: StringProperty()
    fog_volume_depth: StringProperty()

    # OBB
    obb_volume_type: StringProperty()

    # MESH LEVEL
    # ---------------------------------
    face_type: StringProperty()
    face_mode: StringProperty()
    face_sides: StringProperty()
    region_name: StringProperty()
    face_global_material: StringProperty()
    sky_permutation_index: StringProperty()
    ladder: StringProperty()
    slip_surface: StringProperty()
    decal_offset: StringProperty()
    no_shadow: StringProperty()
    precise_position: StringProperty()
    no_lightmap: StringProperty()
    no_pvs: StringProperty()
    mesh_compression: StringProperty()

    # LIGHTMAP
    lightmap_additive_transparency: StringProperty()
    lightmap_resolution_scale: StringProperty()
    lightmap_photon_fidelity: StringProperty()
    lightmap_type: StringProperty()
    lightmap_analytical_bounce_modifier: StringProperty()
    lightmap_general_bounce_modifier: StringProperty()
    lightmap_translucency_tint_color: StringProperty()
    lightmap_lighting_from_both_sides: StringProperty()

    # EMISSIVE
    material_lighting_attenuation_cutoff: StringProperty()
    material_lighting_attenuation_falloff: StringProperty()
    material_lighting_emissive_focus: StringProperty()
    material_lighting_emissive_color: StringProperty()
    material_lighting_emissive_per_unit: StringProperty()
    material_lighting_emissive_power: StringProperty()
    material_lighting_emissive_quality: StringProperty()
    material_lighting_use_shader_gel: StringProperty()
    material_lighting_bounce_ratio: StringProperty()

    # MARKER LEVEL
    marker_all_regions: StringProperty()
    marker_game_instance_tag_name: StringProperty()
    marker_game_instance_tag_variant_name: StringProperty()
    marker_game_instance_run_scripts: StringProperty()
    marker_hint_length: StringProperty()
    marker_sphere_radius: StringProperty()
    marker_velocity: StringProperty()
    marker_pathfinding_sphere_vehicle: StringProperty()
    pathfinding_sphere_remains_when_open: StringProperty()
    pathfinding_sphere_with_sectors: StringProperty()
    physics_constraint_parent: StringProperty()
    physics_constraint_child: StringProperty()
    physics_constraint_type: StringProperty()
    physics_constraint_uses_limits: StringProperty()
    hinge_constraint_minimum: StringProperty()
    hinge_constraint_maximum: StringProperty()
    cone_angle: StringProperty()
    plane_constraint_minimum: StringProperty()
    plane_constraint_maximum: StringProperty()
    twist_constraint_start: StringProperty()
    twist_constraint_end: StringProperty()
    marker_looping_effect: StringProperty()
    marker_light_cone_tag: StringProperty()
    marker_light_cone_color: StringProperty()
    marker_light_cone_alpha: StringProperty()
    marker_light_cone_width: StringProperty()
    marker_light_cone_length: StringProperty()
    marker_light_cone_intensity: StringProperty()
    marker_light_cone_curve: StringProperty()

    # ANIMATION EVENTS
    event_id: IntProperty()
    event_type: StringProperty()
    frame_start: StringProperty()
    frame_end: StringProperty()
    wrinkle_map_face_region: StringProperty()
    wrinkle_map_effect: StringProperty()
    footstep_type: StringProperty()
    footstep_effect: StringProperty()
    ik_chain: StringProperty()
    ik_active_tag: StringProperty()
    ik_target_tag: StringProperty()
    ik_target_marker: StringProperty()
    ik_target_usage: StringProperty()
    ik_proxy_target_id: StringProperty()
    ik_pole_vector_id: StringProperty()
    ik_effector_id: StringProperty()
    cinematic_effect_tag: StringProperty()
    cinematic_effect_effect: StringProperty()
    cinematic_effect_marker: StringProperty()
    object_function_name: StringProperty()
    object_function_effect: StringProperty()
    frame_frame: IntProperty()
    frame_name: StringProperty()
    frame_trigger: StringProperty()
    import_frame: StringProperty()
    import_name: StringProperty()
    text: StringProperty()
    is_animation_event: BoolProperty()
    
    # ANIMATION CONTROLS
    animation_control_type: StringProperty()
    animation_control_id: StringProperty()
    animation_control_ik_chain: StringProperty()
    animation_control_ik_effect: StringProperty()
    animation_control_constraint_effect: StringProperty()
    animation_control_proxy_target_marker: StringProperty()
    animation_control_proxy_target_tag: StringProperty()
    animation_control_proxy_target_usage: StringProperty()

    # Object stuff needed for face properties

    # INSTANCED GEOMETRY ONLY

    instanced_collision: BoolProperty(
        name="Bullet Collision",
    )
    instanced_physics: BoolProperty(
        name="Player Collision",
    )

    cookie_cutter: BoolProperty(
        name="Cookie Cutter",
    )

    #########

    toggle_face_defaults: BoolProperty()

    # MARKER PERMS
    marker_exclude_permutations : StringProperty()
    marker_include_permutations : StringProperty()


# LIGHT PROPERTIES
# ----------------------------------------------------------


class NWO_LightPropertiesGroup(PropertyGroup):
    # LIGHTS #
    light_type_override: EnumProperty(
        name="Light Type",
        options=set(),
        description="Displays the light type. Use the blender light types to change the value of this field",
        default="_connected_geometry_light_type_omni",
        items=[
            ("_connected_geometry_light_type_spot", "Spot", ""),
            ("_connected_geometry_light_type_directional", "Directional", ""),
            ("_connected_geometry_light_type_omni", "Point", ""),
        ],
    )

    light_game_type: EnumProperty(
        name="Light Game Type",
        options=set(),
        description="",
        default="_connected_geometry_bungie_light_type_default",
        items=[
            ("_connected_geometry_bungie_light_type_default", "Default", ""),
            ("_connected_geometry_bungie_light_type_inlined", "Inlined", ""),
            ("_connected_geometry_bungie_light_type_rerender", "Rerender", ""),
            (
                "_connected_geometry_bungie_light_type_screen_space",
                "Screen Space",
                "",
            ),
            ("_connected_geometry_bungie_light_type_uber", "Uber", ""),
        ],
    )

    light_shape: EnumProperty(
        name="Light Shape",
        options=set(),
        description="",
        default="_connected_geometry_light_shape_circle",
        items=[
            ("_connected_geometry_light_shape_circle", "Circle", ""),
            ("_connected_geometry_light_shape_rectangle", "Rectangle", ""),
        ],
    )
    
    def update_light_near_attenuation_start(self, context):
        if self.light_near_attenuation_start > self.light_near_attenuation_end:
            self.light_near_attenuation_end = self.light_near_attenuation_start

    light_near_attenuation_start: FloatProperty(
        name="Light Activation Start",
        options=set(),
        description="The power of the light remains zero up until this point",
        default=0,
        min=0,
        subtype='DISTANCE',
        unit='LENGTH',
        update=update_light_near_attenuation_start,
    )
    
    def update_light_near_attenuation_end(self, context):
        if self.light_near_attenuation_end > self.light_far_attenuation_start:
            self.light_far_attenuation_start = self.light_near_attenuation_end
        elif self.light_near_attenuation_end < self.light_near_attenuation_start:
            self.light_near_attenuation_start = self.light_near_attenuation_end

    light_near_attenuation_end: FloatProperty(
        name="Light Activation End",
        options=set(),
        description="From the light activation start, light power gradually increases up until the end point",
        default=0,
        min=0,
        subtype='DISTANCE',
        unit='LENGTH',
        update=update_light_near_attenuation_end,
    )
    
    def update_light_far_attenuation_start(self, context):
        if self.light_far_attenuation_start > self.light_far_attenuation_end:
            self.light_far_attenuation_end = self.light_far_attenuation_start
        elif self.light_far_attenuation_start < self.light_near_attenuation_end:
            self.light_near_attenuation_end = self.light_far_attenuation_start

    light_far_attenuation_start: FloatProperty(
        name="Light Falloff Start",
        options=set(),
        description="After this point, the light will begin to lose power",
        default=0,
        min=0,
        subtype='DISTANCE',
        unit='LENGTH',
        update=update_light_far_attenuation_start,
    )
    
    def update_light_far_attenuation_end(self, context):
        if self.light_far_attenuation_end < self.light_far_attenuation_start:
            self.light_far_attenuation_start = self.light_far_attenuation_end

    light_far_attenuation_end: FloatProperty(
        name="Light Falloff End",
        options=set(),
        description="From the light falloff start, the light will gradually lose power until it reaches zero by the end point. Setting this to 0 will let the game automatically calculate light falloff based on intensity",
        default=0,
        min=0,
        subtype='DISTANCE',
        unit='LENGTH',
        update=update_light_far_attenuation_end,
    )

    light_volume_distance: FloatProperty(
        name="Light Volume Distance",
        options=set(),
        description="",
    )

    light_volume_intensity: FloatProperty(
        name="Light Volume Intensity",
        options=set(),
        description="",
        default=1.0,
        min=0.0,
        soft_max=10.0,
        subtype="FACTOR",
    )

    light_fade_start_distance: FloatProperty(
        name="Light Fade Out Start",
        options=set(),
        description="The light starts to fade out when the camera is x units away",
        default=wu(100),
        subtype='DISTANCE',
        unit='LENGTH',
    )

    light_fade_end_distance: FloatProperty(
        name="Light Fade Out End",
        options=set(),
        description="The light completely fades out when the camera is x units away",
        default=wu(150),
        subtype='DISTANCE',
        unit='LENGTH',
    )

    light_ignore_bsp_visibility: BoolProperty(
        name="Light Ignore BSP Visibility",
        options=set(),
        description="",
        default=False,
    )
    
    def get_light_intensity(self):
        return calc_light_intensity(self.id_data)
    
    def set_light_intensity(self, value):
        self['light_intensity_value'] = value
        
    def update_light_intensity(self, context):
        self.id_data.energy = calc_light_energy(self.id_data, self.light_intensity_value)

    light_intensity: FloatProperty(
        name="Light Intensity",
        options=set(),
        description="The intensity of this light expressed in the units the game uses",
        get=get_light_intensity,
        set=set_light_intensity,
        update=update_light_intensity,
    )
    
    light_intensity_value: FloatProperty(options={'HIDDEN'})

    light_use_clipping: BoolProperty(
        name="Light Uses Clipping",
        options=set(),
        description="",
        default=False,
    )

    light_clipping_size_x_pos: FloatProperty(
        name="Light Clipping Size X Forward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_y_pos: FloatProperty(
        name="Light Clipping Size Y Forward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_z_pos: FloatProperty(
        name="Light Clipping Size Z Forward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_x_neg: FloatProperty(
        name="Light Clipping Size X Backward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_y_neg: FloatProperty(
        name="Light Clipping Size Y Backward",
        options=set(),
        description="",
        default=100,
    )

    light_clipping_size_z_neg: FloatProperty(
        name="Light Clipping Size Z Backward",
        options=set(),
        description="",
        default=100,
    )

    light_hotspot_size: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=25,
    )

    light_hotspot_falloff: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=80,
    )

    light_falloff_shape: FloatProperty(
        name="Light Falloff Shape",
        options=set(),
        description="",
        default=1,
        min=0.0,
        soft_max=10.0,
        subtype="FACTOR",
    )

    light_aspect: FloatProperty(
        name="Light Aspect",
        options=set(),
        description="",
        default=1,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )

    light_frustum_width: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=1.0,
    )

    light_frustum_height: FloatProperty(
        name="Light Hotspot Size",
        options=set(),
        description="",
        default=1.0,
    )

    light_bounce_ratio: FloatProperty(
        name="Light Falloff Shape",
        options=set(),
        description="",
        default=1,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )

    light_dynamic_has_bounce: BoolProperty(
        name="Light Has Dynamic Bounce",
        options=set(),
        description="",
        default=False,
    )

    light_screenspace_has_specular: BoolProperty(
        name="Screenspace Light Has Specular",
        options=set(),
        description="",
        default=False,
    )

    def light_tag_clean_tag_path(self, context):
        self["light_tag_override"] = clean_tag_path(self["light_tag_override"]).strip(
            '"'
        )

    light_tag_override: StringProperty(
        name="Light Tag Override",
        options=set(),
        description="",
        update=light_tag_clean_tag_path,
    )

    def light_shader_clean_tag_path(self, context):
        self["light_shader_reference"] = clean_tag_path(
            self["light_shader_reference"]
        ).strip('"')

    light_shader_reference: StringProperty(
        name="Light Shader Reference",
        options=set(),
        description="",
        update=light_shader_clean_tag_path,
    )

    def light_gel_clean_tag_path(self, context):
        self["light_gel_reference"] = clean_tag_path(self["light_gel_reference"]).strip(
            '"'
        )

    light_gel_reference: StringProperty(
        name="Light Gel Reference",
        options=set(),
        description="",
        update=light_gel_clean_tag_path,
    )

    def light_lens_flare_clean_tag_path(self, context):
        self["light_lens_flare_reference"] = clean_tag_path(
            self["light_lens_flare_reference"]
        ).strip('"')

    light_lens_flare_reference: StringProperty(
        name="Light Lens Flare Reference",
        options=set(),
        description="",
        update=light_lens_flare_clean_tag_path,
    )

    # H4 LIGHT PROPERTIES
    light_dynamic_shadow_quality: EnumProperty(
        name="Shadow Quality",
        options=set(),
        description="",
        default="_connected_geometry_dynamic_shadow_quality_normal",
        items=[
            (
                "_connected_geometry_dynamic_shadow_quality_normal",
                "Normal",
                "",
            ),
            (
                "_connected_geometry_dynamic_shadow_quality_expensive",
                "Expensive",
                "",
            ),
        ],
    )

    light_specular_contribution: BoolProperty(
        name="Specular Contribution",
        options=set(),
        description="",
        default=False,
    )

    light_amplification_factor: FloatProperty(
        name="Indirect Amplification",
        options=set(),
        description="",
        default=0.5,
        subtype="FACTOR",
        min=0.0,
        soft_max=10.0,
    )

    light_attenuation_near_radius: FloatProperty(
        name="Near Attenuation Radius",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_attenuation_far_radius: FloatProperty(
        name="Far Attenuation Radius",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_attenuation_power: FloatProperty(
        name="Attenuation Power",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_cinema_objects_only: BoolProperty(
        name="Only Light Cinematic Objects",
        options=set(),
        description="",
        default=False,
    )

    light_tag_name: StringProperty(
        name="Light Tag Name",
        options=set(),
        description="",
    )

    light_specular_power: FloatProperty(
        name="Specular Power",
        options=set(),
        description="",
        default=32,
        min=0.0,
    )

    light_specular_intensity: FloatProperty(
        name="Specular Intensity",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )
    
    light_camera_fade_start: FloatProperty(
        name="Camera Fade Start",
        description="Distance at which this light begins to fade from the camera view",
        options=set(),
        default=0,
        min=0,
    )
    
    light_camera_fade_end: FloatProperty(
        name="Camera Fade End",
        description="Distance at which this light is completely invisible from the camera view",
        options=set(),
        default=0,
        min=0,
    )

    light_cinema: EnumProperty(
        name="Cinematic Render",
        options=set(),
        description="Define whether this light should only render in cinematics, outside of cinematics, or always render",
        default="_connected_geometry_lighting_cinema_default",
        items=[
            ("_connected_geometry_lighting_cinema_default", "Always", ""),
            (
                "_connected_geometry_lighting_cinema_only",
                "Cinematics Only",
                "",
            ),
            ("_connected_geometry_lighting_cinema_exclude", "Exclude", ""),
        ],
    )

    light_cone_projection_shape: EnumProperty(
        name="Cone Projection Shape",
        options=set(),
        description="",
        default="_connected_geometry_cone_projection_shape_cone",
        items=[
            ("_connected_geometry_cone_projection_shape_cone", "Cone", ""),
            (
                "_connected_geometry_cone_projection_shape_frustum",
                "Frustum",
                "",
            ),
        ],
    )

    light_shadow_near_clipplane: FloatProperty(
        name="Shadow Near Clip Plane",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_jitter_sphere_radius: FloatProperty(
        name="Light Jitter Sphere Radius",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_shadow_far_clipplane: FloatProperty(
        name="Shadow Far Clip Plane",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_shadow_bias_offset: FloatProperty(
        name="Shadow Bias Offset",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_shadow_color: FloatVectorProperty(
        name="Shadow Color",
        options=set(),
        description="",
        default=(0.0, 0.0, 0.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    light_shadows: BoolProperty(
        name="Has Shadows",
        options=set(),
        description="",
        default=True,
    )

    light_sub_type: EnumProperty(
        name="Light Sub-Type",
        options=set(),
        description="",
        default="_connected_geometry_lighting_sub_type_default",
        items=[
            ("_connected_geometry_lighting_sub_type_default", "Default", ""),
            (
                "_connected_geometry_lighting_sub_type_screenspace",
                "Screenspace",
                "",
            ),
            ("_connected_geometry_lighting_sub_type_uber", "Uber", ""),
        ],
    )

    light_ignore_dynamic_objects: BoolProperty(
        name="Ignore Dynamic Objects",
        options=set(),
        description="",
        default=False,
    )

    light_diffuse_contribution: BoolProperty(
        name="Diffuse Contribution",
        options=set(),
        description="",
        default=True,
    )

    light_destroy_after: FloatProperty(
        name="Destroy After (seconds)",
        options=set(),
        description="Destroy the light after x seconds. 0 means the light is never destroyed",
        subtype="TIME",
        unit="TIME",
        step=100,
        default=0,
        min=0.0,
    )

    light_jitter_angle: FloatProperty(
        name="Light Jitter Angle",
        options=set(),
        description="",
        default=0,
        min=0.0,
    )

    light_jitter_quality: EnumProperty(
        name="Light Jitter Quality",
        options=set(),
        description="",
        default="_connected_geometry_light_jitter_quality_high",
        items=[
            ("_connected_geometry_light_jitter_quality_low", "Low", ""),
            ("_connected_geometry_light_jitter_quality_medium", "Medium", ""),
            ("_connected_geometry_light_jitter_quality_high", "High", ""),
        ],
    )

    light_indirect_only: BoolProperty(
        name="Indirect Only",
        options=set(),
        description="",
        default=False,
    )

    light_screenspace: BoolProperty(
        name="Screenspace Light",
        options=set(),
        description="",
        default=False,
    )

    light_intensity_off: BoolProperty(
        name="Set Via Tag",
        options=set(),
        description="Stops this value being passed to the game. Use if you want to set the intensity manually in the tag (such as if you want to make use of functions for lights)",
        default=False,
    )

    near_attenuation_end_off: BoolProperty(
        name="Set Via Tag",
        options=set(),
        description="Stops this value being passed to the game. Use if you want to set the near attenuation end manually in the tag (such as if you want to make use of functions for lights)",
        default=False,
    )

    outer_cone_angle_off: BoolProperty(
        name="Set Via Tag",
        options=set(),
        description="Stops this value being passed to the game. Use if you want to set the outer cone angle manually in the tag (such as if you want to make use of functions for lights)",
        default=False,
    )

    manual_fade_distance: BoolProperty(
        name="Specify Fade Out Distance",
        options=set(),
        description="Reveals fade out distance settings",
        default=False,
    )

    light_static_analytic: BoolProperty(
        name="Static Analytic",
        options=set(),
        description="",
        default=False,
    )

    light_mode: EnumProperty(
        name="Light Mode",
        options=set(),
        description="",
        default="_connected_geometry_light_mode_static",
        items=[
            (
                "_connected_geometry_light_mode_static",
                "Static",
                "Lights used in lightmapping",
            ),
            (
                "_connected_geometry_light_mode_dynamic",
                "Dynamic",
                "Lights that appear regardless of whether the map has been lightmapped",
            ),
            ("_connected_geometry_light_mode_analytic", "Analytic", ""),
        ],
    )

# BONE PROPS
# ----------------------------------------------------------
class NWO_BonePropertiesGroup(PropertyGroup):
    # name_override: StringProperty(
    #     name="Name Override",
    #     description="Set the Halo export name for this bone. Allowing you to use blender friendly naming conventions for bones while rigging/animating",
    #     default="",
    # )
    frame_id1: StringProperty(
        name="Frame ID 1",
        description="The Frame ID 1 for this bone. Leave blank for automatic assignment of a Frame ID. Can be manually edited when using expert mode, but don't do this unless you know what you're doing",
        default="",
    )
    frame_id2: StringProperty(
        name="Frame ID 2",
        description="The Frame ID 2 for this bone. Leave blank for automatic assignment of a Frame ID. Can be manually edited when using expert mode, but don't do this unless you know what you're doing",
        default="",
    )
    object_space_node: BoolProperty(
        name="Object Space Offset Node",
        description="",
        default=False,
        options=set(),
    )
    replacement_correction_node: BoolProperty(
        name="Replacement Correction Node",
        description="",
        default=False,
        options=set(),
    )
    fik_anchor_node: BoolProperty(
        name="Forward IK Anchor Node",
        description="",
        default=False,
        options=set(),
    )
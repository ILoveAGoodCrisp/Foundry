from math import radians
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
from ..utils import (
    calc_light_energy,
    clean_tag_path,
    dot_partition,
    calc_light_intensity,
    get_exclude_collections,
    get_object_type,
    get_prop_from_collection,
    is_mesh,
    wu,
)

# MESH PROPS
# ----------------------------------------------------------

class NWO_MeshPropertiesGroup(PropertyGroup):
    proxy_collision: PointerProperty(type=bpy.types.Object)
    proxy_physics: PointerProperty(type=bpy.types.Object)
    proxy_cookie_cutter: PointerProperty(type=bpy.types.Object)
    
    mesh_type: StringProperty(
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
        options=set(),
    )
    
    face_draw_distance: EnumProperty(
        name="Draw Distance Limit",
        options=set(),
        description="Controls the distance at which faces will stop rendering",
        items=[
            ('_connected_geometry_face_draw_distance_normal', 'Default', ''),
            ('_connected_geometry_face_draw_distance_detail_mid', 'Medium', ''),
            ('_connected_geometry_face_draw_distance_detail_close', 'Close', ''),
        ]
    )

    highlight: BoolProperty(
        options=set(),
        name="Highlight",
    )
    
    face_global_material: StringProperty(
        name="Collision Material",
        default="",
        description="A material used for collision and physics meshes to control material responses to projectiles and physics objects, and seperates a model for the purpose of damage regions. If the name matches a valid material defined in tags\globals\globals.globals then this mesh will automatically take the correct material response type, otherwise, the material override can be manually defined in the .model tag in materials tag block",
    )

    mesh_face: EnumProperty(
        name="Mesh | Face",
        items=[
            ("mesh", "MOP", "Mesh Object Properties"),
            ("face", "FLOP", "Face Level Object Properties"),
        ],
        options=set(),
    )

    def update_face_type(self, context):
        self.face_type_active = True
    
    def poop_collision_type_items(self, context):
        items = []
        items.append(("_connected_geometry_poop_collision_type_default", "Full", "Collision mesh that interacts with the physics objects and with projectiles"))
        items.append(("_connected_geometry_poop_collision_type_invisible_wall", "Sphere Collision", "Collision mesh that interacts with the physics objects only"))
        items.append(("_connected_geometry_poop_collision_type_play_collision", "Player Collision", "Collision mesh that affects physics objects and physical projectiles, such as grenades"))
        items.append(("_connected_geometry_poop_collision_type_bullet_collision", "Bullet Collision", "Collision mesh that only interacts with simple projectiles, such as bullets"))
        
        return items
        
    poop_collision_type: EnumProperty(
        name="Collision Type",
        options=set(),
        description="",
        items=poop_collision_type_items,
    )
    
    render_only: BoolProperty(
        name="No Collision",
        description="Game will not build a collision representation of this mesh. It will not be collidable in game",
        options=set(),
    )
    
    sphere_collision_only: BoolProperty(
        name="Sphere Collision Only",
        description="Only physics objects collide with this mesh. Projectiles will pass through it",
        options=set(),
    )
    
    collision_only: BoolProperty(
        name="Collision Only",
        description="Collision only. Physics objects and projectiles will collide with this but it will not be visible",
        options=set(),
    )
    
    breakable: BoolProperty(
        name="Breakable",
        description="Allows collision geometry to be destroyed",
        options=set(),
    )

    face_two_sided: BoolProperty(
        name="Two Sided",
        description="Render the backfacing normal of this mesh if it has render geometry. Collision geometry will be two-sided and will not result in open edges, but will be more expensive",
        options=set(),
    )

    face_transparent: BoolProperty(
        name="Transparent",
        description="Game treats this mesh as being see through. If you're using a shader/material which has transparency, set this flag. This does not affect visible transparency",
        options=set(),
    )

    face_two_sided_type: EnumProperty(
        name="Two Sided Policy",
        description="Changes the apparance of back facing normals on a two-sided mesh",
        options=set(),
        items=[
            ("two_sided", "Default", "No special properties"),
            ("mirror", "Mirror", "Mirror backside normals from the frontside"),
            ("keep", "Keep", "Keep the same normal on each face side"),
        ]
    )

    ladder: BoolProperty(
        name="Ladder",
        options=set(),
        description="Climbable collision geometry",
    )

    slip_surface: BoolProperty(
        name="Slip Surface",
        options=set(),
        description="Units will slip off this if the incline is at least 35 degrees",
    )


    decal_offset: BoolProperty(
        name="Decal Offset",
        options=set(),
        description="This gives the mesh a small offset from its game calculated position, so that it avoids z-fighting with another mesh",
        default=False,
    )
    
    no_shadow: BoolProperty(
        name="No Shadow",
        options=set(),
        description="Prevents the mesh from casting shadows",
    )

    precise_position: BoolProperty(
        name="Uncompressed",
        options=set(),
        description="Lowers the degree of compression of vertices during export, resulting in more accurate (and expensive) meshes in game. Only use this when you need to",
    )

    no_lightmap: BoolProperty(
        name="Exclude From Lightmap",
        options=set(),
        description="Exclude mesh from lightmapping",
    )

    no_pvs: BoolProperty(
        name="Invisible To PVS",
        options=set(),
        description="Mesh is unaffected by Potential Visbility Sets - the games render culling system",
    )
    
    def update_lightmap_additive_transparency(self, context):
        self.lightmap_additive_transparency_active = True

    lightmap_additive_transparency_active: BoolProperty()
    lightmap_additive_transparency: FloatVectorProperty(
        name="lightmap Additive Transparency",
        options=set(),
        description="Overrides the amount and color of light that will pass through the surface. Tint color will override the alpha blend settings in the shader",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        update=update_lightmap_additive_transparency,
    )

    def update_lightmap_ignore_default_resolution_scale(self, context):
        self.lightmap_ignore_default_resolution_scale_active = True

    lightmap_ignore_default_resolution_scale_active: BoolProperty()
    lightmap_ignore_default_resolution_scale: BoolProperty(
        name="Lightmap Resolution Scale",
        options=set(),
        description="",
        default=False,
        update=update_lightmap_ignore_default_resolution_scale,
    )

    def update_lightmap_resolution_scale(self, context):
        self.lightmap_resolution_scale_active = True

    lightmap_resolution_scale_active: BoolProperty()
    lightmap_resolution_scale: IntProperty(
        name="Resolution Scale",
        options=set(),
        default=3,
        min=1,
        max=7,
        description="Determines how much texel space the faces will be given on the lightmap. 1 means less space for the faces, while 7 means more space for the faces. The relationships can be tweaked in the .scenario tag under the bsp tag block",
        update=update_lightmap_resolution_scale,
    )

    def update_lightmap_photon_fidelity(self, context):
        self.lightmap_photon_fidelity_active = True

    # lightmap_photon_fidelity_active: BoolProperty()
    # lightmap_photon_fidelity: EnumProperty(
    #     name="Photon Fidelity",
    #     options=set(),
    #     update=update_lightmap_photon_fidelity,
    #     description="H4+ only",
    #     default="_connected_material_lightmap_photon_fidelity_normal",
    #     items=[
    #         (
    #             "_connected_material_lightmap_photon_fidelity_normal",
    #             "Normal",
    #             "",
    #         ),
    #         (
    #             "_connected_material_lightmap_photon_fidelity_medium",
    #             "Medium",
    #             "",
    #         ),
    #         ("_connected_material_lightmap_photon_fidelity_high", "High", ""),
    #         ("_connected_material_lightmap_photon_fidelity_none", "None", ""),
    #     ],
    # )

    def update_lightmap_type(self, context):
        self.lightmap_type_active = True

    lightmap_type_active: BoolProperty()
    lightmap_type: EnumProperty(
        name="Lightmap Type",
        options=set(),
        update=update_lightmap_type,
        description="How this should be lit while lightmapping",
        default="_connected_material_lightmap_type_per_pixel",
        items=[
            ("_connected_material_lightmap_type_per_pixel", "Per Pixel", "Per pixel provides good fidelity and lighting variation but it takes up resolution in the lightmap bitmap"),
            ("_connected_material_lightmap_type_per_vertex", "Per Vertex", "Uses a separate and additional per-vertex lightmap budget. Cost is dependent purely on complexity/vert count of the mesh"),
        ],
    )

    lightmap_transparency_override: BoolProperty(
        name="Lightmap Transparency Override",
        options=set(),
        description="",
        default=False,
    )

    def update_lightmap_analytical_bounce_modifier(self, context):
        self.lightmap_analytical_bounce_modifier_active = True

    lightmap_analytical_bounce_modifier_active: BoolProperty()
    lightmap_analytical_bounce_modifier: FloatProperty(
        name="Lightmap Analytical Bounce Modifier",
        options=set(),
        description="",
        default=1,
        update=update_lightmap_analytical_bounce_modifier,
    )

    def update_lightmap_general_bounce_modifier(self, context):
        self.lightmap_general_bounce_modifier_active = True

    lightmap_general_bounce_modifier_active: BoolProperty()
    lightmap_general_bounce_modifier: FloatProperty(
        name="Lightmap General Bounce Modifier",
        options=set(),
        description="",
        default=1,
        update=update_lightmap_general_bounce_modifier,
    )

    def update_lightmap_translucency_tint_color(self, context):
        self.lightmap_translucency_tint_color_active = True

    lightmap_translucency_tint_color_active: BoolProperty()
    lightmap_translucency_tint_color: FloatVectorProperty(
        name="Lightmap Translucency Tint Color",
        options=set(),
        description="",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        update=update_lightmap_translucency_tint_color,
    )

    def update_lightmap_lighting_from_both_sides(self, context):
        self.lightmap_lighting_from_both_sides_active = True

    lightmap_lighting_from_both_sides_active: BoolProperty()
    lightmap_lighting_from_both_sides: BoolProperty(
        name="Lightmap Lighting From Both Sides",
        options=set(),
        description="",
        default=False,
        update=update_lightmap_lighting_from_both_sides,
    )

    # MATERIAL LIGHTING PROPERTIES

    emissive_active: BoolProperty()
    material_lighting_attenuation_active: BoolProperty()
            
    def update_lighting_attenuation_falloff(self, context):
        if not context.scene.nwo.transforming:
            if self.material_lighting_attenuation_falloff > self.material_lighting_attenuation_cutoff:
                self.material_lighting_attenuation_cutoff = self.material_lighting_attenuation_falloff
            
    def update_lighting_attenuation_cutoff(self, context):
        if not context.scene.nwo.transforming:
            if self.material_lighting_attenuation_cutoff < self.material_lighting_attenuation_falloff:
                self.material_lighting_attenuation_falloff = self.material_lighting_attenuation_cutoff
    
    material_lighting_attenuation_cutoff: FloatProperty(
        name="Material Lighting Attenuation Cutoff",
        options=set(),
        description="Determines how far light travels before it stops. Leave this at 0 to for realistic light falloff/cutoff",
        min=wu(8),
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

    material_lighting_attenuation_falloff: FloatProperty(
        name="Material Lighting Attenuation Falloff",
        options=set(),
        description="Determines how far light travels before its power begins to falloff",
        min=0,
        default=wu(2),
        update=update_lighting_attenuation_falloff,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    material_lighting_emissive_focus_active: BoolProperty()
    material_lighting_emissive_focus: FloatProperty(
        name="Material Lighting Emissive Focus",
        options=set(),
        description="Controls the spread of the light. 180 degrees will emit light in a hemisphere from each point, 0 degrees will emit light nearly perpendicular to the surface",
        min=0,
        default=radians(180), 
        max=radians(180),
        subtype="ANGLE",
    )

    material_lighting_emissive_color_active: BoolProperty()
    material_lighting_emissive_color: FloatVectorProperty(
        name="Material Lighting Emissive Color",
        options=set(),
        description="The RGB value of the emitted light",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    material_lighting_emissive_per_unit_active: BoolProperty()
    material_lighting_emissive_per_unit: BoolProperty(
        name="Material Lighting Emissive Per Unit",
        options=set(),
        description="When an emissive surface is scaled, determines if the amount of emitted light should be spread out across the surface or increased/decreased to keep a regular amount of light emission per unit area",
        default=False,
    )

    material_lighting_emissive_power_active: BoolProperty()
    material_lighting_emissive_power: FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="",
        min=0,
        default=5,
        # update=update_emissive,
    )

    material_lighting_emissive_quality_active: BoolProperty()
    material_lighting_emissive_quality: FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="Controls the quality of the shadows cast by a complex occluder. For instance, a light casting shadows of tree branches on a wall would require a higher quality to get smooth shadows",
        default=1,
        min=0,
    )

    material_lighting_use_shader_gel_active: BoolProperty()
    material_lighting_use_shader_gel: BoolProperty(
        name="Material Lighting Use Shader Gel",
        options=set(),
        description="",
        default=False,
    )

    material_lighting_bounce_ratio_active: BoolProperty()
    material_lighting_bounce_ratio: FloatProperty(
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
    scale_model: BoolProperty(options={'HIDDEN'})
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
        options=set(),
    )

    marker_permutation_type: EnumProperty(
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
    
    #########################################################################################################################
    # MESH TYPE UI ####################################################################################################
    #########################################################################################################################
    
    def get_mesh_type(self):
        if not is_mesh(self.id_data):
            return '_connected_geometry_mesh_type_none'
        
        return self.id_data.data.nwo.mesh_type

    mesh_type: StringProperty(
        name="Mesh Type",
        default='_connected_geometry_mesh_type_default',
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_mesh_type,
    )

    #########################################################################################################################
    # MARKER TYPE UI ####################################################################################################
    #########################################################################################################################

    marker_type: StringProperty(
        name="Marker Type",
        options=set(),
        default='_connected_geometry_marker_type_model',
    )

    marker_type_help: IntProperty(options=set())
    
    frame_override: BoolProperty(
        name="Frame Override",
        description="Sets this empty as a frame regardless of whether it has children",
    )

    export_this: BoolProperty(
        name="Export",
        default=True,
        description="Whether this object is exported or not",
        options=set(),
    )
    
    emissive_active: BoolProperty(options=set())
    
    def get_exportable(self):
        if not self.export_this:
            return False
        ob = self.id_data
        ob: bpy.types.Object
        if get_object_type(ob) == '_connected_geometry_object_type_none':
            return False
        if not ob.users_collection:
            return False
        
        if not bpy.context.view_layer.objects.get(ob.name):
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

    # OBJECT LEVEL PROPERTIES

    seam_back: StringProperty(
        name="Seam Back Facing BSP",
        default="default",
        description="The BSP that the normals of this seam are facing away from",
        options=set(),
    )
    
    seam_back_manual: BoolProperty(
        name="Manual Seam Backface",
        description="Seam backface is defined by a separate seam object",
        options=set(),
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

    mesh_primitive_type: EnumProperty(
        name="Mesh Primitive Type",
        options=set(),
        description="If this is not none then the in game physics shape will be simplified to the selected primitive, using the objects dimensions",
        items=mesh_primitive_type_items,
    )
    
    mopp_physics: BoolProperty(
        name="Allow Non-Convex Shape",
        options=set(),
        description="Tells the game to generate a physics representation of this mesh without converting it to a convex hull",
    )

    mesh_tessellation_density: EnumProperty(
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
            "_connected_geometry_poop_lighting_per_pixel",
            "Per Pixel",
            "Per pixel provides good fidelity and lighting variation but it takes up resolution in the lightmap bitmap",
        ),
        (
            "_connected_geometry_poop_lighting_per_vertex",
            "Per Vertex",
            "Uses a separate and additional per-vertex lightmap budget. Cost is dependent purely on complexity/vert count of the mesh",
        ),
        (
            "_connected_geometry_poop_lighting_single_probe",
            "Single Probe",
            "Cheap but effective lighting",
        ),
    ]

    # POOP PROPERTIES
    poop_render_only: BoolProperty(
        name="Render Only",
        options=set(),
        description="Instance is render only regardless of whether the underlying mesh itself has collision",
    )
    
    poop_lighting: EnumProperty(
        name="Lighting Policy",
        options=set(),
        description="Determines how this instance is lightmapped",
        default="_connected_geometry_poop_lighting_per_pixel",
        items=poop_lighting_items,
    )
    
    poop_ao: BoolProperty(
        name="Ambient Occlusion",
        options=set(),
        description="Per vertex lighting gets ambient occlusion only",
    )

    poop_lightmap_resolution_scale: IntProperty(
        name="Lightmap Resolution",
        options=set(),
        description="Determines how much texel space the faces will be given on the lightmap. 1 means less space for the faces, while 7 means more space for the faces. The relationships can be tweaked in the .scenario tag under the bsp tag block",
        default=3,
        min=1,
        max=7,
    )

    poop_pathfinding_items = [
        (
            "_connected_poop_instance_pathfinding_policy_cutout",
            "Cutout",
            "AI will be able to pathfind around this instance, but not on it",
        ),
        (
            "_connected_poop_instance_pathfinding_policy_none",
            "None",
            "This instance will be ignored during pathfinding generation. AI will attempt to walk though it as if it is not there",
        ),
        (
            "_connected_poop_instance_pathfinding_policy_static",
            "Static",
            "AI will be able to pathfind around and on this instance",
        ),
    ]

    poop_pathfinding: EnumProperty(
        name="Instanced Geometry Pathfinding",
        options=set(),
        description="How this instanced is assessed when the game builds a pathfinding representation of the map",
        default="_connected_poop_instance_pathfinding_policy_cutout",
        items=poop_pathfinding_items,
    )

    poop_imposter_policy: EnumProperty(
        name="Instanced Geometry Imposter Policy",
        options=set(),
        description="Sets what kind of imposter model is assigned to this instance. If any the policy is set to anything other than 'Never', you will need to generate imposters for this to render correctly. See https://c20.reclaimers.net/hr/guides/imposter-generation/ for how to generate these",
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

    poop_imposter_brightness: FloatProperty(  # h4+
        name="Imposter Brightness",
        options=set(),
        description="The brightness of the imposter variant of this instance",
        default=0.0,
        min=0.0,
    )

    poop_imposter_transition_distance: FloatProperty(
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

    poop_streaming_priority: EnumProperty(  # h4+
        name="Streaming Priority",
        options=set(),
        description="When the game loads textures it will prioritise textures on those objects with a higher streaming priority",
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

    reach_poop_collision : BoolProperty(options={'HIDDEN'}) # INTERNAL

    poop_chops_portals: BoolProperty(
        name="Chops Portals",
        options=set(),
        description="Doesn't work",
        default=False,
    )

    poop_does_not_block_aoe: BoolProperty(
        name="Does Not Block AOE",
        options=set(),
        description="Instance does not block area of effect damage",
        default=False,
    )

    poop_excluded_from_lightprobe: BoolProperty(
        name="Excluded From Lightprobe",
        options=set(),
        description="Instanced geometry to be excluded from any lightprobes (e.g. placed airprobes)",
        default=False,
    )

    poop_decal_spacing: BoolProperty(
        name="Decal Spacing",
        options=set(),
        description="Gives this instance a small offset from its game calculated position, so that it avoids z-fighting with another mesh",
        default=False,
    )

    poop_remove_from_shadow_geometry: BoolProperty(  # H4+
        name="Dynamic Sun Shadow",
        options=set(),
        description="Shadows cast by this object are dynamic. Useful for example on tree leaves with foliage materials",
        default=False,
    )

    poop_disallow_lighting_samples: BoolProperty(  # H4+
        name="",
        options=set(),
        description="",
        default=False,
    )

    poop_cinematic_properties: EnumProperty(  # h4+
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
    portal_type: EnumProperty(
        name="Portal Type",
        options=set(),
        description="Determines how this portal handles visibilty culling",
        default="_connected_geometry_portal_type_two_way",
        items=[
            (
                "_connected_geometry_portal_type_no_way",
                "No Way",
                "Blocks all visibility",
            ),
            (
                "_connected_geometry_portal_type_one_way",
                "One Way",
                "Allows visibility through the front face (i.e the front facing normal), but culls visibility when viewed from the opposite side",
            ),
            (
                "_connected_geometry_portal_type_two_way",
                "Two Way",
                "Allows visibilty when viewed from either side",
            ),
        ],
    )

    portal_ai_deafening: BoolProperty(
        name="AI Deafening",
        options=set(),
        description="Stops AI hearing through this portal",
        default=False,
    )

    portal_blocks_sounds: BoolProperty(
        name="Blocks Sounds",
        options=set(),
        description="Stops sound from travelling past this portal",
        default=False,
    )

    portal_is_door: BoolProperty(
        name="Is Door",
        options=set(),
        description="Portal visibility is attached to a device machine state",
        default=False,
    )

    # DECORATOR PROPERTIES
    decorator_lod: EnumProperty(
        name="Decorator Level of Detail",
        options=set(),
        description="Level of detail of this object. The game will switch to this LOD at the appropriate range",
        items=[
            ("high", "High", ""),
            ("medium", "Medium", ""),
            ("low", "Low", ""),
            ("very_low", "Very Low", ""),
        ]
    )

    # WATER VOLUME PROPERTIES
    water_volume_depth: FloatProperty(  # this something which can probably be automated?
        name="Water Volume Depth",
        options=set(),
        description="How deep the water physics volume extends",
        default=wu(20),
        subtype='DISTANCE'
    )
    water_volume_flow_direction: FloatProperty(  # this something which can probably be automated?
        name="Water Volume Flow Direction",
        options=set(),
        description="The flow direction of this water volume mesh. It will carry physics objects in this direction. 0 matches the scene forward direction",
        subtype='ANGLE',
    )

    water_volume_flow_velocity: FloatProperty(
        name="Water Volume Flow Velocity",
        options=set(),
        description="Velocity of the water flow physics",
        default=1,
    )

    water_volume_fog_color: FloatVectorProperty(
        name="Water Volume Fog Color",
        options=set(),
        description="Color of the fog that renders when below the water surface",
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    water_volume_fog_murkiness: FloatProperty(
        name="Water Volume Fog Murkiness",
        options=set(),
        description="How murky, i.e. opaque, the underwater fog appears",
        default=0.5,
        subtype="FACTOR",
        min=0.0,
        max=1.0,
    )

    def fog_clean_tag_path(self, context):
        self["fog_appearance_tag"] = clean_tag_path(
            self["fog_appearance_tag"]
        ).strip('"')

    fog_appearance_tag: StringProperty(
        name="Fog Appearance Tag",
        description="Link the planar fog parameters tag that provides settings for this fog volume",
        update=fog_clean_tag_path,
    )

    fog_volume_depth: FloatProperty(
        name="Fog Volume Depth",
        options=set(),
        description="How deep the fog volume volume extends",
        default=20,
    )

    marker_uses_regions: BoolProperty(
        name="Marker All Regions",
        options=set(),
        description="Link this object to a specific region and consequently, permutation(s)",
        default=False,
    )
    
    def get_marker_model_group(self):
        stripped_name = dot_partition(self.id_data.name).strip("#_?$-")
        if self.marker_type == '_connected_geometry_marker_type_effects':
            if not stripped_name.startswith('fx_'):
                return "fx_" + stripped_name
        elif self.marker_type == '_connected_geometry_marker_type_garbage':
            if not stripped_name.startswith('garbage_'):
                return "garbage_" + stripped_name
                
        return stripped_name
    
    marker_model_group: StringProperty(
        name="Marker Group",
        description="The group this marker is assigned to. Defined by the Blender object name, ignoring any characters after the last period (if any) and legacy object prefix/suffixes [#_?$-]",
        get=get_marker_model_group,
    )

    def game_instance_clean_tag_path(self, context):
        self["marker_game_instance_tag_name"] = clean_tag_path(
            self["marker_game_instance_tag_name"]
        ).strip('"')

    marker_game_instance_tag_name: StringProperty(
        name="Marker Game Instance Tag",
        description="Reference to the tag that should be placed at this marker in your scenario",
        update=game_instance_clean_tag_path,
    )

    marker_game_instance_tag_variant_name: StringProperty(
        name="Marker Game Instance Tag Variant",
        description="Setting this will always create the given object variant provided that this name is a valid variant for the object",
    )

    marker_always_run_scripts: BoolProperty(
        name="Always Run Scripts",
        options=set(),
        description="Tells this game object to always run scripts if it has any",
        default=True,
    )
    
    # Prefab marker specific props
    
    prefab_lightmap_res: IntProperty(
        name="Lightmap Resolution",
        description="Override the lightmap resolution of this prefab instance. 0 for no override. The default lightmap resolution meshes used is 3. Determines how much texel space the faces will be given on the lightmap. 1 means less space for the faces, while 7 means more space for the faces. The relationships can be tweaked in the .scenario tag under the bsp tag block",
        min=0,
        max=7,
    )
    
    prefab_render_only: BoolProperty(
        name="Render Only",
        description="Prefab instance has no collision",
        options=set(),
    )
    prefab_does_not_block_aoe: BoolProperty(
        name="Does Not Block AOE",
        options=set(),
        description="Prefab instance does not block area of effect damage",
        default=False,
    )
    prefab_decal_spacing: BoolProperty(
        name="Decal Spacing",
        options=set(),
        description="Prefab instance set to have decal spacing. This gives the mesh a small offset from its game calculated position, so that it avoids z-fighting with another mesh",
        default=False,
    )
    prefab_remove_from_shadow_geometry: BoolProperty(
        name="Dynamic Sun Shadow",
        options=set(),
        description="Shadows cast by this prefab instance are dynamic. Useful for example on tree leaves with foliage materials",
        default=False,
    )
    prefab_disallow_lighting_samples: BoolProperty(
        name="Disallow Lighting Samples",
        options=set(),
        description="",
        default=False,
    )
    
    prefab_excluded_from_lightprobe: BoolProperty(
        name="Excluded From Lightprobe",
        options=set(),
        description="Prefab instance is excluded from any lightprobes",
        default=False,
    )
    
    prefab_cinematic_properties: EnumProperty(
        name="Cinematic Properties",
        options=set(),
        description="Sets whether the prefab instance should render only in cinematics, only outside of cinematics, or in both environments",
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
    
    prefab_lighting_items = [
        (
            "no_override",
            "No Override",
            "Does not override the lighting policy for this prefab instance",
        ),
        (
            "_connected_geometry_poop_lighting_per_pixel",
            "Per Pixel",
            "Per pixel provides good fidelity and lighting variation but it takes up resolution in the lightmap bitmap",
        ),
        (
            "_connected_geometry_poop_lighting_per_vertex",
            "Per Vertex",
            "Uses a separate and additional per-vertex lightmap budget. Cost is dependent purely on complexity/vert count of the mesh",
        ),
        (
            "_connected_geometry_poop_lighting_single_probe",
            "Single Probe",
            "Cheap but effective lighting",
        ),
    ]

    prefab_lighting: EnumProperty(
        name="Lighting Policy",
        options=set(),
        description="Sets the lighting policy for this prefab instance",
        default="no_override",
        items=prefab_lighting_items,
    )
    
    prefab_ao: BoolProperty(
        name="Ambient Occlusion",
        options=set(),
        description="Per vertex lighting gets ambient occlusion only",
    )

    prefab_pathfinding_items = [
        (
            "no_override",
            "No Override",
            "Does not override the pathfinding policy for this prefab instance",
        ),
        (
            "_connected_poop_instance_pathfinding_policy_cutout",
            "Cutout",
            "Sets the pathfinding policy to cutout. AI will be able to pathfind around this mesh, but not on it.",
        ),
        (
            "_connected_poop_instance_pathfinding_policy_none",
            "None",
            "Sets the pathfinding policy to none. This mesh will be ignored during pathfinding generation",
        ),
        (
            "_connected_poop_instance_pathfinding_policy_static",
            "Static",
            "Sets the pathfinding policy to static. AI will be able to pathfind around and on this mesh",
        ),
    ]

    prefab_pathfinding: EnumProperty(
        name="Pathfinding Policy",
        options=set(),
        description="Sets the pathfinding policy for this prefab instance",
        default="no_override",
        items=prefab_pathfinding_items,
    )

    prefab_imposter_policy: EnumProperty(
        name="Imposter Policy",
        options=set(),
        description="Sets the imposter policy for this prefab instance",
        default="no_override",
        items=[
            (
                "no_override",
                "No Override",
                "Does not override the imposter policy for this prefab instance",
            ),
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

    prefab_imposter_brightness: FloatProperty(
        name="Imposter Brightness",
        options=set(),
        description="Sets the brightness of the imposter variant of this prefab. Leave at zero for no override",
        default=0.0,
        min=0.0,
    )

    prefab_imposter_transition_distance: FloatProperty(
        name="Imposter Transition Distance",
        options=set(),
        description="The distance at which the instanced geometry transitions to its imposter variant",
        default=50,
    )

    prefab_imposter_transition_distance_auto: BoolProperty(
        name="Imposter Transition Override",
        options=set(),
        description="Enable to override the imposter transition distance of this prefab instance",
        default=True,
    )

    prefab_streaming_priority: EnumProperty(
        name="Streaming Priority",
        options=set(),
        description="Sets the streaming priority for this prefab instance",
        default="no_override",
        items=[
            (
                "no_override",
                "No Override",
                "Does not override the streaming priority for this prefab instance",
            ),
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
    
    #####

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

    marker_velocity: FloatVectorProperty(
        name="Marker Velocity",
        options=set(),
        description="Manages the direction and speed with which an object created at this marker is given on spawn",
        subtype="VELOCITY",
    )

    marker_pathfinding_sphere_vehicle: BoolProperty(
        name="Vehicle Only Pathfinding Sphere",
        options=set(),
        description="This pathfinding sphere only affects vehicle pathfinding",
    )

    pathfinding_sphere_remains_when_open: BoolProperty(
        name="Pathfinding Sphere Remains When Open",
        options=set(),
        description="Pathfinding sphere remains even when a machine is open",
    )

    pathfinding_sphere_with_sectors: BoolProperty(
        name="Pathfinding Sphere With Sectors",
        options=set(),
        description="Only active when the pathfinding policy of the object is set to Sectors",
    )
    
    def poll_physics_constraint_target(self, object):
        return object.type == 'ARMATURE' or object.nwo.mesh_type == '_connected_geometry_mesh_type_physics'

    physics_constraint_parent: PointerProperty(
        name="Physics Constraint Parent",
        description="The physics object (or armature and bone) this constraint is attached to",
        type=bpy.types.Object,
        poll=poll_physics_constraint_target,
    )

    physics_constraint_parent_bone: StringProperty(
        name="Physics Constraint Parent Bone",
        description="The bone that is attached to this constaint. The bone must have atleast one physics object child to be valid",
    )

    physics_constraint_child: PointerProperty(
        name="Physics Constraint Child",
        description="The physics object (or armature and bone) this constraint is attached to",
        type=bpy.types.Object,
        poll=poll_physics_constraint_target,
    )

    physics_constraint_child_bone: StringProperty(
        name="Physics Constraint Child Bone",
        description="The bone that is attached to this constaint. The bone must have atleast one physics object child to be valid",
    )

    physics_constraint_type: EnumProperty(
        name="Constraint Type",
        options=set(),
        description="Whether this is a hinge or socket (i.e ragdoll) constraint",
        default="_connected_geometry_marker_type_physics_hinge_constraint",
        items=[
            (
                "_connected_geometry_marker_type_physics_hinge_constraint",
                "Hinge",
                "Constraint that enables rotation around this marker on a single axis",
            ),
            (
                "_connected_geometry_marker_type_physics_socket_constraint",
                "Socket",
                "Constraint that enables rotation around this marker on any axis",
            ),
        ],
    )

    physics_constraint_uses_limits: BoolProperty(
        name="Physics Constraint Uses Limits",
        options=set(),
        description="Allows setting of constraint limits",
    )

    hinge_constraint_minimum: FloatProperty(
        name="Hinge Constraint Minimum",
        options=set(),
        description="Minimum angle of a physics hinge",
        subtype='ANGLE',
        default=radians(-180),
        min=radians(-180),
        max=radians(180),
    )

    hinge_constraint_maximum: FloatProperty(
        name="Hinge Constraint Maximum",
        options=set(),
        description="Maximum angle of a physics hinge",
        subtype='ANGLE',
        default=radians(180),
        min=radians(-180),
        max=radians(180),
    )

    cone_angle: FloatProperty(
        name="Cone Angle",
        options=set(),
        subtype='ANGLE',
        description="Cone angle",
        default=radians(90),
        min=0,
        max=radians(180),
    )

    plane_constraint_minimum: FloatProperty(
        name="Plane Constraint Minimum",
        options=set(),
        description="",
        subtype='ANGLE',
        default=radians(-90),
        min=radians(-90),
        max=0,
    )

    plane_constraint_maximum: FloatProperty(
        name="Plane Constraint Maximum",
        options=set(),
        description="",
        subtype='ANGLE',
        default=radians(90),
        min=0,
        max=radians(90),
    )

    twist_constraint_start: FloatProperty(
        name="Twist Constraint Minimum",
        options=set(),
        subtype='ANGLE',
        description="Starting angle of a twist constraint",
        default=radians(-180),
        min=radians(-180),
        max=radians(180),
    )

    twist_constraint_end: FloatProperty(
        name="Twist Constraint Maximum",
        options=set(),
        description="Ending angle of a twist constraint",
        default=radians(180),
        subtype='ANGLE',
        min=radians(-180),
        max=radians(180),
    )

    def effect_clean_tag_path(self, context):
        self["marker_looping_effect"] = clean_tag_path(
            self["marker_looping_effect"]
        ).strip('"')

    marker_looping_effect: StringProperty(
        name="Effect Path",
        description="Tag path to an effect tag",
        update=effect_clean_tag_path,
    )

    def light_cone_clean_tag_path(self, context):
        self["marker_light_cone_tag"] = clean_tag_path(
            self["marker_light_cone_tag"]
        ).strip('"')

    marker_light_cone_tag: StringProperty(
        name="Light Cone Tag Path",
        description="Tag path to a light cone tag",
        update=light_cone_clean_tag_path,
    )

    marker_light_cone_color: FloatVectorProperty(
        name="Light Cone Color",
        options=set(),
        description="",
        subtype="COLOR",
    )

    # marker_light_cone_alpha: FloatProperty(
    #     name="Light Cone Alpha",
    #     options=set(),
    #     description="",
    #     default=1.0,
    #     subtype="FACTOR",
    #     min=0.0,
    #     max=1.0,
    # )

    marker_light_cone_width: FloatProperty(
        name="Light Cone Width",
        options=set(),
        description="",
        default=5,
        min=0,
    )

    marker_light_cone_length: FloatProperty(
        name="Light Cone Length",
        options=set(),
        description="",
        default=10,
        min=0,
    )

    marker_light_cone_intensity: FloatProperty(
        name="Light Cone Intensity",
        options=set(),
        description="",
        default=1,
        min=0,
    )

    def light_cone_curve_clean_tag_path(self, context):
        self["marker_light_cone_curve"] = clean_tag_path(
            self["marker_light_cone_curve"]
        ).strip('"')

    marker_light_cone_curve: StringProperty(
        name="Light Cone Curve Tag Path",
        description="Tag path to a curve scalar tag",
        update=light_cone_curve_clean_tag_path,
    )

    def get_region_name(self):
        scene_nwo = bpy.context.scene.nwo
        regions = scene_nwo.regions_table
        name = self.get("region_name", "")
        if not regions:
            return "default"
        region_names = [r.name for r in regions]
        old_region_names = [r.old for r in regions]
        if name not in region_names and name not in old_region_names:
            name = scene_nwo.regions_table[0].name
        self['region_name'] = name
        return name

    def set_region_name(self, value):
        self['region_name'] = value

    region_name: StringProperty(
        name="Face Region",
        description="",
        get=get_region_name,
        set=set_region_name,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_region_from_collection(self):
        region = get_prop_from_collection(self.id_data, 'region')
        return region

    region_name_locked: StringProperty(
        name="Face Region",
        description="",
        get=get_region_from_collection,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_permutation_name(self):
        scene_nwo = bpy.context.scene.nwo
        permutations = scene_nwo.permutations_table
        name = self.get("permutation_name", "")
        if not permutations:
            return "default"
        permutation_names = [p.name for p in permutations]
        old_permutation_names = [p.old for p in permutations]
        if name not in permutation_names and name not in old_permutation_names:
            name = scene_nwo.permutations_table[0].name
        self['permutation_name'] = name
        return name

    def set_permutation_name(self, value):
        self['permutation_name'] = value

    permutation_name: StringProperty(
        name="Permutation",
        default="default",
        description="The permutation of this object. Permutations get exported to seperate files in scenario exports, or in model exports if the mesh type is one of render/collision/physics",
        get=get_permutation_name,
        set=set_permutation_name,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_permutation_from_collection(self):
        permutation = get_prop_from_collection(self.id_data, 'permutation')
        return permutation

    permutation_name_locked: StringProperty(
        name="Permutation",
        description="The permutation of this object. Leave blank for default",
        get=get_permutation_from_collection,
        override={'LIBRARY_OVERRIDABLE'},
    )

    is_pca: BoolProperty(
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
            ("_connected_geometry_bungie_light_type_default", "Default", "Lightmap light. Requires lightmapping to complete for this light appear"),
            ("_connected_geometry_bungie_light_type_inlined", "Inlined", "For large lights"),
            ("_connected_geometry_bungie_light_type_rerender", "Rerender", "High quality shadowing light"),
            (
                "_connected_geometry_bungie_light_type_screen_space",
                "Screen Space",
                "Cheap low quality dynamic light",
            ),
            ("_connected_geometry_bungie_light_type_uber", "Uber", "High quality light"),
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
        if not context.scene.nwo.transforming:
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
        if not context.scene.nwo.transforming:
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
        if not context.scene.nwo.transforming:
            if self.light_far_attenuation_start > self.light_far_attenuation_end:
                self.light_far_attenuation_end = self.light_far_attenuation_start
            elif self.light_far_attenuation_start < self.light_near_attenuation_end:
                self.light_near_attenuation_end = self.light_far_attenuation_start

    light_far_attenuation_start: FloatProperty(
        name="Light Falloff Start",
        options=set(),
        description="After this point, the light will begin to lose power",
        default=wu(2),
        min=0,
        subtype='DISTANCE',
        unit='LENGTH',
        update=update_light_far_attenuation_start,
    )
    
    def update_light_far_attenuation_end(self, context):
        if not context.scene.nwo.transforming:
            if self.light_far_attenuation_end < self.light_far_attenuation_start:
                self.light_far_attenuation_start = self.light_far_attenuation_end

    light_far_attenuation_end: FloatProperty(
        name="Light Falloff End",
        options=set(),
        description="From the light falloff start, the light will gradually lose power until it reaches zero by the end point. Setting this to 0 will let the game automatically calculate light falloff based on intensity",
        default=wu(8),
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

    light_bounce_ratio: FloatProperty(
        name="Light Bounce Ratio",
        options=set(),
        description="",
        default=1,
        min=0.0,
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
    
    light_physically_correct: BoolProperty(
        name="Light Physically Correct",
        description="Light uses power to determine light falloff and cutoff",
        options=set(),
    )
    
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
        default=True,
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
        subtype='ANGLE'
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
            ("_connected_geometry_light_mode_analytic", "Analytic", "Similar to static lights but provides better results, however only one analytic light should ever light an object at a time"),
        ],
    )
    
    # Emissive props
    
    light_quality: FloatProperty(
        name="Light Quality",
        options=set(),
        description="Controls the quality of the shadows cast by a complex occluder. For instance, a light casting shadows of tree branches on a wall would require a higher quality to get smooth shadows",
        default=1,
        min=0,
    )
    
    light_focus: FloatProperty(
        name="Light Focus",
        options=set(),
        description="Controls the spread of the light. 180 degrees will emit light in a hemisphere from each point, 0 degrees will emit light nearly perpendicular to the surface",
        min=0,
        default=radians(180), 
        max=radians(180),
        subtype="ANGLE",
    )
    
    light_use_shader_gel: BoolProperty(
        name="Use Shader Gel",
        options=set(),
        description="",
        default=False,
    )
    
    light_per_unit: BoolProperty(
        name="Light Per Unit",
        options=set(),
        description="When an light is scaled, determines if the amount of emitted light should be spread out across the surface or increased/decreased to keep a regular amount of light emission per unit area",
        default=False,
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
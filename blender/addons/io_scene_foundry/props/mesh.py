"""Mesh and face level properties"""

from math import radians
import bpy

from ..tools.property_apply import apply_props_material_data

from ..icons import get_icon_id

from .. import utils

class NWO_FaceProperties_ListItems(bpy.types.PropertyGroup):
    layer_name: bpy.props.StringProperty()
    face_count: bpy.props.IntProperty(
        options=set(),
    )
    layer_color: bpy.props.FloatVectorProperty(
        subtype="COLOR_GAMMA",
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0,
        max=1,
        options=set(),
    )
    name: bpy.props.StringProperty()
    face_two_sided_override: bpy.props.BoolProperty()
    face_transparent_override: bpy.props.BoolProperty()
    face_draw_distance_override: bpy.props.BoolProperty()
    region_name_override: bpy.props.BoolProperty()
    face_global_material_override: bpy.props.BoolProperty()
    ladder_override: bpy.props.BoolProperty()
    slip_surface_override: bpy.props.BoolProperty()
    breakable_override: bpy.props.BoolProperty()
    decal_offset_override: bpy.props.BoolProperty()
    no_shadow_override: bpy.props.BoolProperty()
    precise_position_override: bpy.props.BoolProperty()
    no_lightmap_override: bpy.props.BoolProperty()
    lightmap_only_override: bpy.props.BoolProperty()
    no_pvs_override: bpy.props.BoolProperty()
    mesh_tessellation_density_override: bpy.props.BoolProperty()
    # lightmap
    lightmap_additive_transparency_override: bpy.props.BoolProperty()
    lightmap_resolution_scale_override: bpy.props.BoolProperty()
    lightmap_type_override: bpy.props.BoolProperty()
    lightmap_analytical_bounce_modifier_override: bpy.props.BoolProperty()
    lightmap_general_bounce_modifier_override: bpy.props.BoolProperty()
    lightmap_translucency_tint_color_override: bpy.props.BoolProperty()
    lightmap_transparency_override_override: bpy.props.BoolProperty()
    lightmap_lighting_from_both_sides_override: bpy.props.BoolProperty()
    lightmap_ignore_default_resolution_scale_override: bpy.props.BoolProperty()
    # material lighting
    emissive_override: bpy.props.BoolProperty()
    # Collision stuff
    render_only_override: bpy.props.BoolProperty()
    collision_only_override: bpy.props.BoolProperty()
    sphere_collision_only_override: bpy.props.BoolProperty()
    player_collision_only_override: bpy.props.BoolProperty()
    bullet_collision_only_override: bpy.props.BoolProperty()
    
    render_only: bpy.props.BoolProperty()
    collision_only: bpy.props.BoolProperty()
    sphere_collision_only: bpy.props.BoolProperty()
    player_collision_only: bpy.props.BoolProperty()
    bullet_collision_only: bpy.props.BoolProperty()

    face_two_sided: bpy.props.BoolProperty(
        name="Two Sided",
        description="Render the backfacing normal of this mesh, or if this mesh is collision, prevent open edges being treated as such in game",
        options=set(),
    )

    face_transparent: bpy.props.BoolProperty(
        name="Transparent",
        description="Game treats this mesh as being transparent. If you're using a shader/material which has transparency, set this flag",
        options=set(),
    )

    face_two_sided_type: bpy.props.EnumProperty(
        name="Two Sided Policy",
        description="Set how the game should render the opposite side of mesh faces",
        options=set(),
        items=[
            ("two_sided", "Default", "No special properties"),
            ("mirror", "Mirror", "Mirror backside normals from the frontside"),
            ("keep", "Keep", "Keep the same normal on each face side"),
        ]
    )
    
    def update_region_name(self, context):
        if self.name.startswith("region::"):
            self.name = "region::" + self.region_name

    region_name: bpy.props.StringProperty(
        name="Region",
        default="default",
        description="The name of the region these faces should be associated with",
        update=update_region_name,
    )
    
    def update_face_draw_distance(self, context):
        if self.name.startswith("Draw Distance::"):
            self.name = "Draw Distance::" + self.mesh_tessellation_density.rpartition("_")[2]
    
    face_draw_distance: bpy.props.EnumProperty(
        name="Draw Distance",
        update=update_face_draw_distance,
        options=set(),
        description="Controls the distance at which the assigned faces will stop rendering",
        items=[
            ('_connected_geometry_face_draw_distance_normal', 'Default', ''),
            ('_connected_geometry_face_draw_distance_detail_mid', 'Medium', ''),
            ('_connected_geometry_face_draw_distance_detail_close', 'Close', ''),
        ]
    )
    
    def update_face_global_material(self, context):
        if self.name.startswith("material::"):
            self.name = "material::" + self.face_global_material

    face_global_material: bpy.props.StringProperty(
        name="Collision Material",
        default="",
        description="A material used for collision and physics meshes to control material responses to projectiles and physics objects, and seperates a model for the purpose of damage regions. If the name matches a valid material defined in tags\globals\globals.globals then this mesh will automatically take the correct material response type, otherwise, the material override can be manually defined in the .model tag in materials tag block",
        update=update_face_global_material,
    )

    ladder: bpy.props.BoolProperty(
        name="Ladder",
        options=set(),
        description="Makes faces climbable",
        default=True,
    )

    slip_surface: bpy.props.BoolProperty(
        name="Slip Surface",
        options=set(),
        description="Assigned faces will be non traversable by the player. Used to ensure the player can not climb a surface regardless of slope angle",
        default=True,
    )

    decal_offset: bpy.props.BoolProperty(
        name="Decal Offset",
        options=set(),
        description="Provides a Z bias to the faces that will not be overridden by the plane build.  If placing a face coplanar against another surface, this flag will prevent Z fighting",
        default=True,
    )
    
    no_shadow: bpy.props.BoolProperty(
        name="No Shadow",
        options=set(),
        description="Prevents faces from casting shadows",
        default=True,
    )

    precise_position: bpy.props.BoolProperty(
        name="Precise Position",
        options=set(),
        description="Disables compression of vertices during export, resulting in more accurate (and expensive) meshes in game. Only use this when you need to",
        default=True,
    )

    no_lightmap: bpy.props.BoolProperty(
        name="Exclude From Lightmap",
        options=set(),
        description="",
        default=True,
    )
    
    lightmap_only: bpy.props.BoolProperty(
        name="Lightmap Only",
        options=set(),
        description="Geometry is non-rendered and non-collidable. This mesh will still be used by the lightmapper for emissive materials",
    )

    no_pvs: bpy.props.BoolProperty(
        name="Invisible To PVS",
        options=set(),
        description="",
        default=True,
    )
    
    def update_mesh_tessellation_density(self, context):
        if self.name.startswith("Tesselation::"):
            self.name = "Tesselation::" + self.mesh_tessellation_density.rpartition("_")[2]
    
    mesh_tessellation_density: bpy.props.EnumProperty(
        name="Mesh Tessellation Density",
        update=update_mesh_tessellation_density,
        options=set(),
        description="Let's tesselate",
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
    
    # Face type
    seam_sealer_override: bpy.props.BoolProperty(options={'HIDDEN'})
    sky_override: bpy.props.BoolProperty(options={'HIDDEN'})
    sky_permutation_index: bpy.props.IntProperty(options={'HIDDEN'})
    

    #########

    # LIGHTMAP

    lightmap_additive_transparency: bpy.props.FloatVectorProperty(
        name="Additive Transparency",
        options=set(),
        description="Overrides the amount and color of light that will pass through the surface. Tint color will override the alpha blend settings in the shader.",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )
    
    lightmap_ignore_default_resolution_scale: bpy.props.BoolProperty(
        name="Ignore Default Lightmap Resolution Scale",
        options=set(),
        description="Different render mesh types can have different default lightmap resolutions. Enabling this prevents the default for a given type being used",
        default=True,
    )

    lightmap_resolution_scale: bpy.props.IntProperty(
        name="Resolution Scale",
        options=set(),
        description="Determines how much texel space the faces will be given on the lightmap.  1 means less space for the faces, while 7 means more space for the faces. The relationships can be tweaked in the .scenario tag",
        default=3,
        min=0,
        max=7,
    )

    lightmap_photon_fidelity: bpy.props.EnumProperty(
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

    # Lightmap_Chart_Group: bpy.props.IntProperty(
    #     name="Lightmap Chart Group",
    #     options=set(),
    #     description="",
    #     default=3,
    #     min=1,
    # )

    lightmap_type: bpy.props.EnumProperty(
        name="Lightmap Type",
        options=set(),
        description="Sets how this should be lit while lightmapping",
        default="_connected_material_lightmap_type_per_pixel",
        items=[
            ("_connected_material_lightmap_type_per_pixel", "Per Pixel", ""),
            ("_connected_material_lightmap_type_per_vertex", "Per Vetex", ""),
        ],
    )
    
    lightmap_transparency_override: bpy.props.BoolProperty(
        name="Disable Lightmap Transparency",
        options=set(),
        description="Disables the transparency of any mesh faces this property is applied for the purposes of lightmapping. For example on a mesh using an invisible shader/material, shadow will still be cast",
        default=True,
    )

    lightmap_analytical_bounce_modifier: bpy.props.FloatProperty(
        name="Lightmap Analytical Bounce Modifier",
        options=set(),
        description="For analytical lights such as the sun. 0 will bounce no energy. 1 will bounce full energy",
        default=1,
        max=1,
        min=0,
        subtype='FACTOR',
    )

    lightmap_general_bounce_modifier: bpy.props.FloatProperty(
        name="Lightmap General Bounce Modifier",
        options=set(),
        description="For analytical lights such as the sun. 0 will bounce no energy. 1 will bounce full energy",
        default=1,
        max=1,
        min=0,
        subtype='FACTOR',
    )

    lightmap_translucency_tint_color: bpy.props.FloatVectorProperty(
        name="Translucency Tint Color",
        options=set(),
        description="Overrides the color of the shadow and color of light after it passes through a surface",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    lightmap_lighting_from_both_sides: bpy.props.BoolProperty(
        name="Lighting From Both Sides",
        options=set(),
        description="",
        default=True,
    )

    # MATERIAL LIGHTING
    
    def update_lighting_attenuation_falloff(self, context):
        if not context.scene.nwo.transforming:
            if self.material_lighting_attenuation_falloff > self.material_lighting_attenuation_cutoff:
                self.material_lighting_attenuation_cutoff = self.material_lighting_attenuation_falloff
            
    def update_lighting_attenuation_cutoff(self, context):
        if not context.scene.nwo.transforming:
            if self.material_lighting_attenuation_cutoff < self.material_lighting_attenuation_falloff:
                self.material_lighting_attenuation_falloff = self.material_lighting_attenuation_cutoff

    material_lighting_attenuation_cutoff: bpy.props.FloatProperty(
        name="Light Cutoff",
        options=set(),
        description="Determines how far light travels before it stops. Leave this at 0 to for realistic light falloff/cutoff",
        min=0,
        default=0,
        update=update_lighting_attenuation_cutoff,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    material_lighting_attenuation_falloff: bpy.props.FloatProperty(
        name="Light Falloff",
        options=set(),
        description="Determines how far light travels before its power begins to falloff",
        min=0,
        default=0,
        update=update_lighting_attenuation_falloff,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    material_lighting_emissive_focus: bpy.props.FloatProperty(
        name="Material Lighting Emissive Focus",
        options=set(),
        description="Controls the spread of the light. 180 degrees will emit light in a hemisphere from each point, 0 degrees will emit light nearly perpendicular to the surface",
        min=0,
        default=radians(180), 
        max=radians(180),
        subtype="ANGLE",
    )

    material_lighting_emissive_color: bpy.props.FloatVectorProperty(
        name="Emissive Color",
        options=set(),
        description="The RGB value of the emitted light",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    material_lighting_emissive_per_unit: bpy.props.BoolProperty(
        name="Emissive Per Unit",
        options=set(),
        description="When an emissive surface is scaled, determines if the amount of emitted light should be spread out across the surface or increased/decreased to keep a regular amount of light emission per unit area",
        default=False,
    )

    material_lighting_emissive_power: bpy.props.FloatProperty(
        name="Emissive Power",
        options=set(),
        description="The power of the emissive surface",
        min=0,
        default=10,
        subtype='POWER',
        unit='POWER',
    )
    
    def get_light_intensity(self):
        return utils.calc_emissive_intensity(self.material_lighting_emissive_power, utils.get_export_scale(bpy.context) ** 2)
    
    def set_light_intensity(self, value):
        self['light_intensity_value'] = value
        
    def update_light_intensity(self, context):
        self.material_lighting_emissive_power = utils.calc_emissive_energy(self.material_lighting_emissive_power, utils.get_export_scale(context) ** -2 * self.light_intensity_value)

    light_intensity: bpy.props.FloatProperty(
        name="Light Intensity",
        options=set(),
        description="The intensity of this light expressed in the units the game uses",
        get=get_light_intensity,
        set=set_light_intensity,
        update=update_light_intensity,
        min=0,
    )
    
    light_intensity_value: bpy.props.FloatProperty(options={'HIDDEN'})

    material_lighting_emissive_quality: bpy.props.FloatProperty(
        name="Emissive Quality",
        options=set(),
        description="Controls the quality of the shadows cast by a complex occluder. For instance, a light casting shadows of tree branches on a wall would require a higher quality to get smooth shadows",
        default=1,
        min=0,
    )

    material_lighting_use_shader_gel: bpy.props.BoolProperty(
        name="Use Shader Gel",
        options=set(),
        description="",
        default=False,
    )

    material_lighting_bounce_ratio: bpy.props.FloatProperty(
        name="Lighting Bounce Ratio",
        options=set(),
        description="0 will bounce no energy. 1 will bounce full energy. Any value greater than 1 will exaggerate the amount of bounced light. Affects 1st bounce only",
        default=1,
        min=0,
    )


class NWO_MeshPropertiesGroup(bpy.types.PropertyGroup):
    proxy_collision: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_cookie_cutter: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics0: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics1: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics2: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics3: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics4: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics5: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics6: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics7: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics8: bpy.props.PointerProperty(type=bpy.types.Object)
    proxy_physics9: bpy.props.PointerProperty(type=bpy.types.Object)
    
    from_vert_normals: bpy.props.BoolProperty(
        name="Uses Custom Vertex Normals",
        description="True if this mesh uses vertex custom normals. This will only take effect if the mesh has custom normals. Only set this manually if you know what you are doing"
    )
    
    def update_obb_volume_type(self, context):
        if utils.get_prefs().apply_materials:
            _, material = utils.mesh_and_material(self.obb_volume_type.lower(), context)
            apply_props_material_data(self.id_data, material)
    
    def obb_volume_types(self, context) -> list:
        return [
            ('LIGHTMAP_EXCLUSION', "Lightmap Exclusion", "", get_icon_id("lightmap_exclude"), 0),
            ('STREAMING_VOLUME', "Texture Streaming", "", get_icon_id("streaming"), 1),
        ]
    
    obb_volume_type: bpy.props.EnumProperty(
        name="Type",
        items=obb_volume_types,
        update=update_obb_volume_type,
        default=0,
        options=set(),
    )
    
    def update_boundary_surface_types(self, context):
        if utils.get_prefs().apply_materials:
            _, material = utils.mesh_and_material(self.boundary_surface_type.lower(), context)
            apply_props_material_data(self.id_data, material)
            
    
    def boundary_surface_types(self, context) -> list:
        return [
            ('SOFT_CEILING', "Soft Ceiling", "", get_icon_id("soft_ceiling"), 0),
            ('SOFT_KILL', "Kill Timer", "", get_icon_id("soft_kill"), 1),
            ('SLIP_SURFACE', "Slip Surface", "", get_icon_id("slip_surface"), 2)
        ]
    
    boundary_surface_type: bpy.props.EnumProperty(
        name="Type",
        items=boundary_surface_types,
        update=update_boundary_surface_types,
        default=0,
        options=set(),
    )
    
    mesh_type: bpy.props.StringProperty(
        name="Mesh Type",
        default='_connected_geometry_mesh_type_default',
        options=set(),
    )

    face_props: bpy.props.CollectionProperty(
        type=NWO_FaceProperties_ListItems, override={"USE_INSERTION"}
    )

    face_props_active_index: bpy.props.IntProperty(
        name="Index for Face Property",
        default=0,
        min=0,
        options=set(),
    )
    
    face_draw_distance: bpy.props.EnumProperty(
        name="Draw Distance",
        options=set(),
        description="Controls the distance at which faces will stop rendering",
        items=[
            ('_connected_geometry_face_draw_distance_normal', 'Default', ''),
            ('_connected_geometry_face_draw_distance_detail_mid', 'Medium', ''),
            ('_connected_geometry_face_draw_distance_detail_close', 'Close', ''),
        ]
    )

    highlight: bpy.props.BoolProperty(
        options=set(),
        name="Highlight",
    )
    
    face_global_material: bpy.props.StringProperty(
        name="Collision Material",
        default="",
        description="A material used for collision and physics meshes to control material responses to projectiles and physics objects, and seperates a model for the purpose of damage regions. If the name matches a valid material defined in tags\globals\globals.globals then this mesh will automatically take the correct material response type, otherwise, the material override can be manually defined in the .model tag in materials tag block",
    )

    mesh_face: bpy.props.EnumProperty(
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
    
    # face_mode: bpy.props.EnumProperty(
    #     name="Type",
    #     description="Determines the kind of geometry the game will build from this mesh"
    #     items=[
    #         ('_connected_geometry_face_mode_normal', "Render & Collision", "Mesh will be used to build both render geometry and collision"),
    #         ('_connected_geometry_face_mode_render_only', "Render Only", "Mesh will be used to build both render geometry. The game will not build a collision representation of this mesh. It will not be collidable in game"),
    #         ('_connected_geometry_face_mode_collision_only', "Collision Only", "Physics objects and projectiles will collide with this mesh but it will not be visible"),
    #         ('_connected_geometry_face_mode_sphere_collision_only', "Sphere Collision Only", "Only physics objects collide with this mesh. Projectiles will pass through it"),
    #         ('_connected_geometry_face_mode_shadow_only', "Shadow Only", "Mesh will be invisible and uncollidable. It will only be used for shadow casting"),
    #         ('_connected_geometry_face_mode_lightmap_only', "Lightmap Only", "Mesh will be invisible and uncollidable. It will only be used by the lightmapping"),
    #         ('_connected_geometry_face_mode_breakable', "", "Allows collision geometry to be destroyed. Mesh will be used to build both render geometry and collision. This type is non-functional in Halo 4+"),
    #     ]
    # )
        
    poop_collision_type: bpy.props.EnumProperty(
        name="Collision Type",
        options=set(),
        description="",
        items=poop_collision_type_items,
    )
    
    render_only: bpy.props.BoolProperty(
        name="No Collision",
        description="Game will not build a collision representation of this mesh. It will not be collidable in game",
        options=set(),
    )
    
    lightmap_only: bpy.props.BoolProperty(
        name="Lightmap Only",
        description="Geometry is non-rendered and non-collidable. This mesh will still be used by the lightmapper for emissive materials",
        options=set(),
    )
    
    def update_sphere_collision(self, context):
        if self.sphere_collision_only and self.collision_only:
            self['collision_only'] = False
            
    def update_collision(self, context):
        if self.collision_only and self.sphere_collision_only:
            self['sphere_collision_only'] = False
    
    sphere_collision_only: bpy.props.BoolProperty(
        name="Sphere Collision Only",
        description="Only physics objects collide with this mesh. Projectiles will pass through it",
        options=set(),
        update=update_sphere_collision,
    )
    
    collision_only: bpy.props.BoolProperty(
        name="Collision Only",
        description="Physics objects and projectiles will collide with this but it will not be visible",
        options=set(),
        update=update_collision,
    )
    
    breakable: bpy.props.BoolProperty(
        name="Breakable",
        description="Allows collision geometry to be destroyed",
        options=set(),
    )

    face_two_sided: bpy.props.BoolProperty(
        name="Two Sided",
        description="Render the backfacing normal of this mesh if it has render geometry. Collision geometry will be two-sided and will not result in open edges, but will be more expensive",
        options=set(),
    )

    face_transparent: bpy.props.BoolProperty(
        name="Transparent",
        description="Game treats this mesh as being see through. If you're using a shader/material which has transparency, set this flag. This does not affect visible transparency",
        options=set(),
    )

    face_two_sided_type: bpy.props.EnumProperty(
        name="Two Sided Policy",
        description="Changes the apparance of back facing normals on a two-sided mesh",
        options=set(),
        items=[
            ("two_sided", "Default", "No special properties"),
            ("mirror", "Mirror", "Mirror backside normals from the frontside"),
            ("keep", "Keep", "Keep the same normal on each face side"),
        ]
    )

    ladder: bpy.props.BoolProperty(
        name="Ladder",
        options=set(),
        description="Climbable collision geometry",
    )

    slip_surface: bpy.props.BoolProperty(
        name="Slip Surface",
        options=set(),
        description="Units will slip off this if the incline is at least 35 degrees",
    )


    decal_offset: bpy.props.BoolProperty(
        name="Decal Offset",
        options=set(),
        description="This gives the mesh a small offset from its game calculated position, so that it avoids z-fighting with another mesh",
        default=False,
    )
    
    no_shadow: bpy.props.BoolProperty(
        name="No Shadow",
        options=set(),
        description="Prevents the mesh from casting shadows",
    )

    precise_position: bpy.props.BoolProperty(
        name="Precise",
        options=set(),
        description="Lowers the degree of compression of vertices during export, resulting in more accurate (and expensive) meshes in game. Only use this when you need to",
    )
    
    uncompressed: bpy.props.BoolProperty(
        name="Uncompressed",
        options=set(),
        description="Mesh vertex data is stored in an uncompressed format",
    )
    
    additional_compression: bpy.props.EnumProperty(
        name="Additional Compression",
        options=set(),
        description="Additional level of compression to apply to this mesh",
        items=[
            ('default', "Default", ""),
            ('_connected_geometry_mesh_additional_compression_force_on', "Force On", ""),
            ('_connected_geometry_mesh_additional_compression_force_off', "Force Off", ""),
        ]
    )

    no_lightmap: bpy.props.BoolProperty(
        name="Exclude From Lightmap",
        options=set(),
        description="Exclude mesh from lightmapping",
    )

    no_pvs: bpy.props.BoolProperty(
        name="Invisible To PVS",
        options=set(),
        description="Mesh is unaffected by Potential Visbility Sets - the games render culling system",
    )
    
    mesh_tessellation_density: bpy.props.EnumProperty(
        name="Mesh Tessellation Density",
        options=set(),
        description="Let's tesselate",
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
    
    def update_lightmap_additive_transparency(self, context):
        self.lightmap_additive_transparency_active = True

    lightmap_additive_transparency_active: bpy.props.BoolProperty()
    lightmap_additive_transparency: bpy.props.FloatVectorProperty(
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

    lightmap_ignore_default_resolution_scale_active: bpy.props.BoolProperty()
    lightmap_ignore_default_resolution_scale: bpy.props.BoolProperty(
        name="Ignore Default Lightmap Resolution Scale",
        options=set(),
        description="Different render mesh types can have different default lightmap resolutions. Enabling this prevents the default for a given type being used",
        default=True,
        update=update_lightmap_ignore_default_resolution_scale,
    )

    def update_lightmap_resolution_scale(self, context):
        self.lightmap_resolution_scale_active = True

    lightmap_resolution_scale_active: bpy.props.BoolProperty()
    lightmap_resolution_scale: bpy.props.IntProperty(
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

    # lightmap_photon_fidelity_active: bpy.props.BoolProperty()
    # lightmap_photon_fidelity: bpy.props.EnumProperty(
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

    lightmap_type_active: bpy.props.BoolProperty()
    lightmap_type: bpy.props.EnumProperty(
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
    
    def update_lightmap_transparency_override(self, context):
        self.lightmap_transparency_override_active = True

    lightmap_transparency_override_active: bpy.props.BoolProperty()
    lightmap_transparency_override: bpy.props.BoolProperty(
        name="Disable Lightmap Transparency",
        options=set(),
        description="Disables the transparency of any mesh faces this property is applied for the purposes of lightmapping. For example on a mesh using an invisible shader/material, shadow will still be cast",
        default=True,
        update=update_lightmap_transparency_override,
    )

    def update_lightmap_analytical_bounce_modifier(self, context):
        self.lightmap_analytical_bounce_modifier_active = True

    lightmap_analytical_bounce_modifier_active: bpy.props.BoolProperty()
    lightmap_analytical_bounce_modifier: bpy.props.FloatProperty(
        name="Lightmap Analytical Bounce Modifier",
        options=set(),
        description="For analytical lights such as the sun. 0 will bounce no energy. 1 will bounce full energy",
        default=1,
        max=1,
        min=0,
        subtype='FACTOR',
        update=update_lightmap_analytical_bounce_modifier,
    )

    def update_lightmap_general_bounce_modifier(self, context):
        self.lightmap_general_bounce_modifier_active = True

    lightmap_general_bounce_modifier_active: bpy.props.BoolProperty()
    lightmap_general_bounce_modifier: bpy.props.FloatProperty(
        name="Lightmap General Bounce Modifier",
        options=set(),
        description="For general lights, such as placed spot lights. 0 will bounce no energy. 1 will bounce full energy",
        default=1,
        max=1,
        min=0,
        subtype='FACTOR',
        update=update_lightmap_general_bounce_modifier,
    )

    def update_lightmap_translucency_tint_color(self, context):
        self.lightmap_translucency_tint_color_active = True

    lightmap_translucency_tint_color_active: bpy.props.BoolProperty()
    lightmap_translucency_tint_color: bpy.props.FloatVectorProperty(
        name="Lightmap Translucency Tint Color",
        options=set(),
        description="Overrides the color of the shadow and color of light after it passes through a surface",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        update=update_lightmap_translucency_tint_color,
    )

    def update_lightmap_lighting_from_both_sides(self, context):
        self.lightmap_lighting_from_both_sides_active = True

    lightmap_lighting_from_both_sides_active: bpy.props.BoolProperty()
    lightmap_lighting_from_both_sides: bpy.props.BoolProperty(
        name="Lightmap Lighting From Both Sides",
        options=set(),
        description="",
        default=True,
        update=update_lightmap_lighting_from_both_sides,
    )

    # MATERIAL LIGHTING PROPERTIES

    emissive_active: bpy.props.BoolProperty()
    material_lighting_attenuation_active: bpy.props.BoolProperty()
            
    def update_lighting_attenuation_falloff(self, context):
        if not context.scene.nwo.transforming:
            if self.material_lighting_attenuation_falloff > self.material_lighting_attenuation_cutoff:
                self.material_lighting_attenuation_cutoff = self.material_lighting_attenuation_falloff
            
    def update_lighting_attenuation_cutoff(self, context):
        if not context.scene.nwo.transforming:
            if self.material_lighting_attenuation_cutoff < self.material_lighting_attenuation_falloff:
                self.material_lighting_attenuation_falloff = self.material_lighting_attenuation_cutoff
    
    material_lighting_attenuation_cutoff: bpy.props.FloatProperty(
        name="Material Lighting Attenuation Cutoff",
        options=set(),
        description="Determines how far light travels before it stops. Leave this at 0 to for realistic light falloff/cutoff",
        min=0,
        default=0,
        update=update_lighting_attenuation_cutoff,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    lighting_attenuation_enabled: bpy.props.BoolProperty(
        name="Use Attenuation",
        options=set(),
        description="Enable / Disable use of attenuation",
        default=True,
    )

    material_lighting_attenuation_falloff: bpy.props.FloatProperty(
        name="Material Lighting Attenuation Falloff",
        options=set(),
        description="Determines how far light travels before its power begins to falloff",
        min=0,
        default=0,
        update=update_lighting_attenuation_falloff,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    material_lighting_emissive_focus_active: bpy.props.BoolProperty()
    material_lighting_emissive_focus: bpy.props.FloatProperty(
        name="Material Lighting Emissive Focus",
        options=set(),
        description="Controls the spread of the light. 180 degrees will emit light in a hemisphere from each point, 0 degrees will emit light nearly perpendicular to the surface",
        min=0,
        default=radians(180), 
        max=radians(180),
        subtype="ANGLE",
    )

    material_lighting_emissive_color_active: bpy.props.BoolProperty()
    material_lighting_emissive_color: bpy.props.FloatVectorProperty(
        name="Material Lighting Emissive Color",
        options=set(),
        description="The RGB value of the emitted light",
        default=(1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    material_lighting_emissive_per_unit_active: bpy.props.BoolProperty()
    material_lighting_emissive_per_unit: bpy.props.BoolProperty(
        name="Material Lighting Emissive Per Unit",
        options=set(),
        description="When an emissive surface is scaled, determines if the amount of emitted light should be spread out across the surface or increased/decreased to keep a regular amount of light emission per unit area",
        default=False,
    )

    material_lighting_emissive_power_active: bpy.props.BoolProperty()
    material_lighting_emissive_power: bpy.props.FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="The power of the emissive surface",
        min=0,
        default=10,
        subtype='POWER',
        unit='POWER',
    )
    
    def get_light_intensity(self):
        return utils.calc_emissive_intensity(self.material_lighting_emissive_power, utils.get_export_scale(bpy.context) ** 2)
    
    def set_light_intensity(self, value):
        self['light_intensity_value'] = value
        
    def update_light_intensity(self, context):
        self.material_lighting_emissive_power = utils.calc_emissive_energy(self.material_lighting_emissive_power, utils.get_export_scale(context) ** -2 * self.light_intensity_value)

    light_intensity: bpy.props.FloatProperty(
        name="Light Intensity",
        options=set(),
        description="The intensity of this light expressed in the units the game uses",
        get=get_light_intensity,
        set=set_light_intensity,
        update=update_light_intensity,
        min=0,
    )
    
    light_intensity_value: bpy.props.FloatProperty(options={'HIDDEN'})

    material_lighting_emissive_quality_active: bpy.props.BoolProperty()
    material_lighting_emissive_quality: bpy.props.FloatProperty(
        name="Material Lighting Emissive Quality",
        options=set(),
        description="Controls the quality of the shadows cast by a complex occluder. For instance, a light casting shadows of tree branches on a wall would require a higher quality to get smooth shadows",
        default=1,
        min=0,
    )

    material_lighting_use_shader_gel_active: bpy.props.BoolProperty()
    material_lighting_use_shader_gel: bpy.props.BoolProperty(
        name="Material Lighting Use Shader Gel",
        options=set(),
        description="",
        default=False,
    )

    material_lighting_bounce_ratio_active: bpy.props.BoolProperty()
    material_lighting_bounce_ratio: bpy.props.FloatProperty(
        name="Material Lighting Bounce Ratio",
        options=set(),
        description="0 will bounce no energy. 1 will bounce full energy. Any value greater than 1 will exaggerate the amount of bounced light. Affects 1st bounce only",
        default=1,
        min=0,
    )
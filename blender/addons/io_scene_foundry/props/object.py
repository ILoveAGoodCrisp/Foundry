from math import radians
import random
import uuid
import bpy
from .. import utils

# MARKER PERM PROPERTIES
# ----------------------------------------------------------
class NWO_MarkerPermutationItems(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Permutation")

# OBJECT PROPERTIES
# ----------------------------------------------------------
class NWO_ObjectPropertiesGroup(bpy.types.PropertyGroup):
    scale_model: bpy.props.BoolProperty(options={'HIDDEN'})
    ### PROXY
    proxy_parent: bpy.props.PointerProperty(type=bpy.types.Mesh)
    proxy_type : bpy.props.StringProperty()
    #### MARKER PERM
    marker_permutations: bpy.props.CollectionProperty(
        type=NWO_MarkerPermutationItems,
    )

    marker_permutations_index: bpy.props.IntProperty(
        name="Index for Animation Event",
        default=0,
        min=0,
        options=set(),
    )

    marker_permutation_type: bpy.props.EnumProperty(
        name="Include/Exclude",
        description="Toggle whether this marker should be included in, or excluded from the below list of permutations. If this is set to include and no permutations are defined, this property will be ignored at export",
        items=[
            ("exclude", "Exclude", ""),
            ("include", "Include", ""),
        ],
        options=set(),
    )
    
    # MAIN
    proxy_instance: bpy.props.BoolProperty(
        name="Proxy Instance",
        description="Duplicates this structure mesh as instanced geometry at export",
        options=set(),
    )
    
    marker_instance: bpy.props.BoolProperty(
        name="Instance Collection is a Marker",
        description="Collection instance is a marker, as opposed a mesh. If this option is off, then the visible mesh will be made real at export",
    )
    
    #########################################################################################################################
    # MESH TYPE UI ####################################################################################################
    #########################################################################################################################
    
    def get_mesh_type(self):
        if not utils.is_mesh(self.id_data):
            return '_connected_geometry_mesh_type_none'
        
        return self.id_data.data.nwo.mesh_type

    mesh_type: bpy.props.StringProperty(
        name="Mesh Type",
        default='_connected_geometry_mesh_type_default',
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_mesh_type,
    )
    
    mesh_type_temp: bpy.props.StringProperty(options={'HIDDEN'})

    #########################################################################################################################
    # MARKER TYPE UI ####################################################################################################
    #########################################################################################################################

    marker_type: bpy.props.StringProperty(
        name="Marker Type",
        options=set(),
        default='_connected_geometry_marker_type_model',
    )

    marker_type_help: bpy.props.IntProperty(options=set())
    
    # frame_override: bpy.props.BoolProperty(
    #     name="Frame Override",
    #     description="Sets this empty as a frame regardless of whether it has children",
    # )

    export_this: bpy.props.BoolProperty(
        name="Export",
        default=True,
        description="Whether this object is exported or not",
        options=set(),
    )
    
    emissive_active: bpy.props.BoolProperty(options=set())
    
    def get_exportable(self):
        if not self.export_this:
            return False
        ob = self.id_data
        ob: bpy.types.Object
        if utils.get_object_type(ob) == '_connected_geometry_object_type_none':
            return False
        if not ob.users_collection:
            return False
        
        if not bpy.context.view_layer.objects.get(ob.name):
            return False
        
        exclude_collections = utils.get_exclude_collections()
        exclude_collections_with_this_ob = [c for c in ob.users_collection if c in exclude_collections]
        if exclude_collections_with_this_ob:
            return False
        
        return True
    
    exportable: bpy.props.BoolProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        get=get_exportable,
    )

    # OBJECT LEVEL PROPERTIES

    seam_back: bpy.props.StringProperty(
        name="Seam Back Facing BSP",
        default="default",
        description="The BSP that the normals of this seam are facing away from",
        options=set(),
    )
    
    seam_back_manual: bpy.props.BoolProperty(
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
    
    def update_mesh_primitive_type(self, context):
        match self.mesh_primitive_type:
            case "_connected_geometry_primitive_type_box":
                utils.set_bounds_display(self.id_data, utils.BoundsDisplay.BOX)
            case "_connected_geometry_primitive_type_pill":
                utils.set_bounds_display(self.id_data, utils.BoundsDisplay.PILL)
            case "_connected_geometry_primitive_type_sphere":
                utils.set_bounds_display(self.id_data, utils.BoundsDisplay.SPHERE)

    mesh_primitive_type: bpy.props.EnumProperty(
        name="Mesh Primitive Type",
        options=set(),
        description="If this is not none then the in game physics shape will be simplified to the selected primitive, using the objects dimensions",
        items=mesh_primitive_type_items,
        # update=update_mesh_primitive_type,
    )
    
    mopp_physics: bpy.props.BoolProperty(
        name="Allow Non-Convex Shape",
        options=set(),
        description="Tells the game to generate a physics representation of this mesh without converting it to a convex hull",
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
    poop_render_only: bpy.props.BoolProperty(
        name="Render Only",
        options=set(),
        description="Instance is render only regardless of whether the underlying mesh itself has collision",
    )
    
    poop_lighting: bpy.props.EnumProperty(
        name="Lighting Policy",
        options=set(),
        description="Determines how this instance is lightmapped",
        default="_connected_geometry_poop_lighting_per_pixel",
        items=poop_lighting_items,
    )
    
    poop_ao: bpy.props.BoolProperty(
        name="Ambient Occlusion",
        options=set(),
        description="Per vertex lighting gets ambient occlusion only",
    )

    poop_lightmap_resolution_scale: bpy.props.IntProperty(
        name="Lightmap Resolution",
        options=set(),
        description="Determines how much texel space the faces will be given on the lightmap. 1 means less space for the faces, while 7 means more space for the faces. The relationships can be tweaked in the .scenario tag under the bsp tag block",
        default=3,
        min=1,
        max=7,
    )
    
    def poop_pathfinding_items(self, context):
        items = []
        if utils.is_corinth(context):
            items.append(("_connected_poop_instance_pathfinding_policy_cutout", "Walkable", "AI will be able to pathfind around and on this mesh"))
            items.append(("_connected_poop_instance_pathfinding_policy_static", "Force Walkable", "AI will be able to pathfind around and on this mesh"))
        else:
            items.append(("_connected_poop_instance_pathfinding_policy_cutout", "Cut-Out", "AI will be able to pathfind around this instance, but not on it"))
            items.append(("_connected_poop_instance_pathfinding_policy_static", "Walkable", "AI will be able to pathfind around and on this mesh"))
        items.append(("_connected_poop_instance_pathfinding_policy_none", "None", "This mesh will be ignored during pathfinding generation. AI will attempt to walk though it as if it is not there"))
        
        return items

    poop_pathfinding: bpy.props.EnumProperty(
        name="Instanced Geometry Pathfinding",
        options=set(),
        description="How this instanced is assessed when the game builds a pathfinding representation of the map",
        items=poop_pathfinding_items,
    )

    poop_imposter_policy: bpy.props.EnumProperty(
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

    poop_imposter_brightness: bpy.props.FloatProperty(  # h4+
        name="Imposter Brightness",
        options=set(),
        description="The brightness of the imposter variant of this instance",
        default=0.0,
        min=0.0,
    )

    poop_imposter_transition_distance: bpy.props.FloatProperty(
        name="Instanced Geometry Imposter Transition Distance",
        options=set(),
        description="The distance at which the instanced geometry transitions to its imposter variant",
        default=50,
    )

    poop_imposter_transition_distance_auto: bpy.props.BoolProperty(
        name="Instanced Geometry Imposter Transition Automatic",
        options=set(),
        description="Enable to let the engine set the imposter transition distance by object size",
        default=True,
    )

    poop_streaming_priority: bpy.props.EnumProperty(  # h4+
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

    reach_poop_collision : bpy.props.BoolProperty(options={'HIDDEN'}) # INTERNAL

    poop_chops_portals: bpy.props.BoolProperty(
        name="Chops Portals",
        options=set(),
        description="Doesn't work",
        default=False,
    )

    poop_does_not_block_aoe: bpy.props.BoolProperty(
        name="Does Not Block AOE",
        options=set(),
        description="Instance does not block area of effect damage",
        default=False,
    )

    poop_excluded_from_lightprobe: bpy.props.BoolProperty(
        name="Excluded From Lightprobe",
        options=set(),
        description="Instanced geometry to be excluded from any lightprobes (e.g. placed airprobes)",
        default=False,
    )

    poop_decal_spacing: bpy.props.BoolProperty(
        name="Decal Spacing",
        options=set(),
        description="Gives this instance a small offset from its game calculated position, so that it avoids z-fighting with another mesh",
        default=False,
    )

    poop_remove_from_shadow_geometry: bpy.props.BoolProperty(  # H4+
        name="Dynamic Sun Shadow",
        options=set(),
        description="Shadows cast by this object are dynamic. Useful for example on tree leaves with foliage materials",
        default=False,
    )

    poop_disallow_lighting_samples: bpy.props.BoolProperty(  # H4+
        name="Disallow Lighting Samples",
        options=set(),
        description="",
        default=False,
    )

    poop_cinematic_properties: bpy.props.EnumProperty(  # h4+
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
    portal_type: bpy.props.EnumProperty(
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

    portal_ai_deafening: bpy.props.BoolProperty(
        name="AI Deafening",
        options=set(),
        description="Stops AI hearing through this portal",
        default=False,
    )

    portal_blocks_sounds: bpy.props.BoolProperty(
        name="Blocks Sounds",
        options=set(),
        description="Stops sound from travelling past this portal",
        default=False,
    )

    portal_is_door: bpy.props.BoolProperty(
        name="Is Door",
        options=set(),
        description="Portal visibility is attached to a device machine state",
        default=False,
    )

    # DECORATOR PROPERTIES
    decorator_lod: bpy.props.EnumProperty(
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
    water_volume_depth: bpy.props.FloatProperty(  # this something which can probably be automated?
        name="Water Volume Depth",
        options=set(),
        description="How deep the water physics volume extends",
        default=utils.wu(20),
        subtype='DISTANCE'
    )
    water_volume_flow_direction: bpy.props.FloatProperty(  # this something which can probably be automated?
        name="Water Volume Flow Direction",
        options=set(),
        description="The flow direction of this water volume mesh. It will carry physics objects in this direction. 0 matches the scene forward direction",
        subtype='ANGLE',
    )

    water_volume_flow_velocity: bpy.props.FloatProperty(
        name="Water Volume Flow Velocity",
        options=set(),
        description="Velocity of the water flow physics",
        default=1,
    )

    water_volume_fog_color: bpy.props.FloatVectorProperty(
        name="Water Volume Fog Color",
        options=set(),
        description="Color of the fog that renders when below the water surface",
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )

    water_volume_fog_murkiness: bpy.props.FloatProperty(
        name="Water Volume Fog Murkiness",
        options=set(),
        description="How murky, i.e. opaque, the underwater fog appears",
        default=0.5,
        subtype="FACTOR",
        min=0.0,
        max=1.0,
    )

    def fog_clean_tag_path(self, context):
        self["fog_appearance_tag"] = utils.clean_tag_path(
            self["fog_appearance_tag"]
        ).strip('"')

    fog_appearance_tag: bpy.props.StringProperty(
        name="Fog Appearance Tag",
        description="Link the planar fog parameters tag that provides settings for this fog volume",
        update=fog_clean_tag_path,
    )

    fog_volume_depth: bpy.props.FloatProperty(
        name="Fog Volume Depth",
        options=set(),
        description="How deep the fog volume volume extends",
        default=20,
    )

    marker_uses_regions: bpy.props.BoolProperty(
        name="Marker All Regions",
        options=set(),
        description="Link this object to a specific region and consequently, permutation(s)",
        default=False,
    )
    
    def get_marker_model_group(self):
        stripped_name = utils.dot_partition(self.id_data.name).strip("#_?$-")
        if self.marker_type == '_connected_geometry_marker_type_effects':
            if not stripped_name.startswith('fx_'):
                return "fx_" + stripped_name
        elif self.marker_type == '_connected_geometry_marker_type_garbage':
            if not stripped_name.startswith('garbage_'):
                return "garbage_" + stripped_name
                
        return stripped_name.lower()
    
    marker_model_group: bpy.props.StringProperty(
        name="Marker Group",
        description="The group this marker is assigned to. Defined by the Blender object name, ignoring any characters after the last period (if any) and legacy object prefix/suffixes [#_?$-]",
        get=get_marker_model_group,
    )

    def game_instance_clean_tag_path(self, context):
        self["marker_game_instance_tag_name"] = utils.clean_tag_path(
            self["marker_game_instance_tag_name"]
        ).strip('"')

    marker_game_instance_tag_name: bpy.props.StringProperty(
        name="Marker Game Instance Tag",
        description="Reference to the tag that should be placed at this marker in your scenario",
        update=game_instance_clean_tag_path,
    )

    marker_game_instance_tag_variant_name: bpy.props.StringProperty(
        name="Marker Game Instance Tag Variant",
        description="Setting this will always create the given object variant provided that this name is a valid variant for the object",
    )

    marker_always_run_scripts: bpy.props.BoolProperty(
        name="Always Run Scripts",
        options=set(),
        description="Tells this game object to always run scripts if it has any",
        default=True,
    )
    
    # Prefab marker specific props
    
    prefab_lightmap_res: bpy.props.IntProperty(
        name="Lightmap Resolution",
        description="Override the lightmap resolution of this prefab instance. 0 for no override. The default lightmap resolution meshes used is 3. Determines how much texel space the faces will be given on the lightmap. 1 means less space for the faces, while 7 means more space for the faces. The relationships can be tweaked in the .scenario tag under the bsp tag block",
        min=0,
        max=7,
        options=set(),
    )
    
    prefab_render_only: bpy.props.BoolProperty(
        name="Render Only",
        description="Prefab instance has no collision",
        options=set(),
    )
    prefab_does_not_block_aoe: bpy.props.BoolProperty(
        name="Does Not Block AOE",
        options=set(),
        description="Prefab instance does not block area of effect damage",
        default=False,
    )
    prefab_decal_spacing: bpy.props.BoolProperty(
        name="Decal Spacing",
        options=set(),
        description="Prefab instance set to have decal spacing. This gives the mesh a small offset from its game calculated position, so that it avoids z-fighting with another mesh",
        default=False,
    )
    prefab_remove_from_shadow_geometry: bpy.props.BoolProperty(
        name="Dynamic Sun Shadow",
        options=set(),
        description="Shadows cast by this prefab instance are dynamic. Useful for example on tree leaves with foliage materials",
        default=False,
    )
    prefab_disallow_lighting_samples: bpy.props.BoolProperty(
        name="Disallow Lighting Samples",
        options=set(),
        description="",
        default=False,
    )
    
    prefab_excluded_from_lightprobe: bpy.props.BoolProperty(
        name="Excluded From Lightprobe",
        options=set(),
        description="Prefab instance is excluded from any lightprobes",
        default=False,
    )
    
    prefab_cinematic_properties: bpy.props.EnumProperty(
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

    prefab_lighting: bpy.props.EnumProperty(
        name="Lighting Policy",
        options=set(),
        description="Sets the lighting policy for this prefab instance",
        default="no_override",
        items=prefab_lighting_items,
    )
    
    prefab_ao: bpy.props.BoolProperty(
        name="Ambient Occlusion",
        options=set(),
        description="Per vertex lighting gets ambient occlusion only",
    )

    def prefab_pathfinding_items(self, context):
        items = []
        items.append(("no_override", "No Override", "Does not override the pathfinding policy for this prefab instance"))
        items.append(("_connected_poop_instance_pathfinding_policy_cutout", "Walkable", "AI will be able to pathfind around and on this mesh"))
        items.append(("_connected_poop_instance_pathfinding_policy_static", "Force Walkable", "AI will be able to pathfind around and on this mesh"))
        items.append(("_connected_poop_instance_pathfinding_policy_none", "None", "This mesh will be ignored during pathfinding generation. AI will attempt to walk though it as if it is not there"))
        
        return items

    prefab_pathfinding: bpy.props.EnumProperty(
        name="Pathfinding Policy",
        options=set(),
        description="Sets the pathfinding policy for this prefab instance",
        items=prefab_pathfinding_items,
    )

    prefab_imposter_policy: bpy.props.EnumProperty(
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

    prefab_imposter_brightness: bpy.props.FloatProperty(
        name="Imposter Brightness",
        options=set(),
        description="Sets the brightness of the imposter variant of this prefab. Leave at zero for no override",
        default=0.0,
        min=0.0,
    )

    prefab_imposter_transition_distance: bpy.props.FloatProperty(
        name="Imposter Transition Distance",
        options=set(),
        description="The distance at which the instanced geometry transitions to its imposter variant",
        default=50,
    )

    prefab_imposter_transition_distance_auto: bpy.props.BoolProperty(
        name="Imposter Transition Override",
        options=set(),
        description="Enable to override the imposter transition distance of this prefab instance",
        default=True,
    )

    prefab_streaming_priority: bpy.props.EnumProperty(
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

    marker_hint_type: bpy.props.EnumProperty(
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

    marker_hint_side: bpy.props.EnumProperty(
        name="Side",
        options=set(),
        description="",
        default="right",
        items=[
            ("right", "Right", ""),
            ("left", "Left", ""),
        ],
    )

    marker_hint_height: bpy.props.EnumProperty(
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

    marker_velocity: bpy.props.FloatVectorProperty(
        name="Marker Velocity",
        options=set(),
        description="Manages the direction and speed with which an object created at this marker is given on spawn",
        subtype="VELOCITY",
    )

    marker_pathfinding_sphere_vehicle: bpy.props.BoolProperty(
        name="Vehicle Only Pathfinding Sphere",
        options=set(),
        description="This pathfinding sphere only affects vehicle pathfinding",
    )

    pathfinding_sphere_remains_when_open: bpy.props.BoolProperty(
        name="Pathfinding Sphere Remains When Open",
        options=set(),
        description="Pathfinding sphere remains even when a machine is open",
    )

    pathfinding_sphere_with_sectors: bpy.props.BoolProperty(
        name="Pathfinding Sphere With Sectors",
        options=set(),
        description="Only active when the pathfinding policy of the object is set to Sectors",
    )
    
    def poll_physics_constraint_target(self, object):
        return object.type == 'ARMATURE' or object.nwo.mesh_type == '_connected_geometry_mesh_type_physics'

    physics_constraint_parent: bpy.props.PointerProperty(
        name="Physics Constraint Parent",
        description="The physics object (or armature and bone) this constraint is attached to",
        type=bpy.types.Object,
        poll=poll_physics_constraint_target,
    )

    physics_constraint_parent_bone: bpy.props.StringProperty(
        name="Physics Constraint Parent Bone",
        description="The bone that is attached to this constaint. The bone must have atleast one physics object child to be valid",
    )

    physics_constraint_child: bpy.props.PointerProperty(
        name="Physics Constraint Child",
        description="The physics object (or armature and bone) this constraint is attached to",
        type=bpy.types.Object,
        poll=poll_physics_constraint_target,
    )

    physics_constraint_child_bone: bpy.props.StringProperty(
        name="Physics Constraint Child Bone",
        description="The bone that is attached to this constaint. The bone must have atleast one physics object child to be valid",
    )

    physics_constraint_type: bpy.props.EnumProperty(
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
                "Constraint that enables rotation around this marker on any axis. For ragdolls",
            ),
        ],
    )

    physics_constraint_uses_limits: bpy.props.BoolProperty(
        name="Physics Constraint Uses Limits",
        options=set(),
        description="Allows setting of constraint limits",
    )

    hinge_constraint_minimum: bpy.props.FloatProperty(
        name="Hinge Constraint Minimum",
        options=set(),
        description="Minimum angle of a physics hinge",
        subtype='ANGLE',
        default=radians(-180),
        min=radians(-180),
        max=radians(180),
    )

    hinge_constraint_maximum: bpy.props.FloatProperty(
        name="Hinge Constraint Maximum",
        options=set(),
        description="Maximum angle of a physics hinge",
        subtype='ANGLE',
        default=radians(180),
        min=radians(-180),
        max=radians(180),
    )

    cone_angle: bpy.props.FloatProperty(
        name="Cone Angle",
        options=set(),
        subtype='ANGLE',
        description="Cone angle",
        default=radians(90),
        min=0,
        max=radians(180),
    )

    plane_constraint_minimum: bpy.props.FloatProperty(
        name="Plane Constraint Minimum",
        options=set(),
        description="",
        subtype='ANGLE',
        default=radians(-90),
        min=radians(-90),
        max=0,
    )

    plane_constraint_maximum: bpy.props.FloatProperty(
        name="Plane Constraint Maximum",
        options=set(),
        description="",
        subtype='ANGLE',
        default=radians(90),
        min=0,
        max=radians(90),
    )

    twist_constraint_start: bpy.props.FloatProperty(
        name="Twist Constraint Minimum",
        options=set(),
        subtype='ANGLE',
        description="Starting angle of a twist constraint",
        default=radians(-180),
        min=radians(-180),
        max=radians(180),
    )

    twist_constraint_end: bpy.props.FloatProperty(
        name="Twist Constraint Maximum",
        options=set(),
        description="Ending angle of a twist constraint",
        default=radians(180),
        subtype='ANGLE',
        min=radians(-180),
        max=radians(180),
    )

    def effect_clean_tag_path(self, context):
        self["marker_looping_effect"] = utils.clean_tag_path(
            self["marker_looping_effect"]
        ).strip('"')

    marker_looping_effect: bpy.props.StringProperty(
        name="Effect Path",
        description="Tag path to an effect tag",
        update=effect_clean_tag_path,
    )

    def light_cone_clean_tag_path(self, context):
        self["marker_light_cone_tag"] = utils.clean_tag_path(
            self["marker_light_cone_tag"]
        ).strip('"')

    marker_light_cone_tag: bpy.props.StringProperty(
        name="Light Cone Tag Path",
        description="Tag path to a light cone tag",
        update=light_cone_clean_tag_path,
    )

    marker_light_cone_color: bpy.props.FloatVectorProperty(
        name="Light Cone Color",
        options=set(),
        description="",
        subtype="COLOR",
    )

    # marker_light_cone_alpha: bpy.props.FloatProperty(
    #     name="Light Cone Alpha",
    #     options=set(),
    #     description="",
    #     default=1.0,
    #     subtype="FACTOR",
    #     min=0.0,
    #     max=1.0,
    # )

    marker_light_cone_width: bpy.props.FloatProperty(
        name="Light Cone Width",
        options=set(),
        description="",
        default=5,
        min=0,
    )

    marker_light_cone_length: bpy.props.FloatProperty(
        name="Light Cone Length",
        options=set(),
        description="",
        default=10,
        min=0,
    )

    marker_light_cone_intensity: bpy.props.FloatProperty(
        name="Light Cone Intensity",
        options=set(),
        description="",
        default=1,
        min=0,
    )

    def light_cone_curve_clean_tag_path(self, context):
        self["marker_light_cone_curve"] = utils.clean_tag_path(
            self["marker_light_cone_curve"]
        ).strip('"')

    marker_light_cone_curve: bpy.props.StringProperty(
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

    region_name: bpy.props.StringProperty(
        name="Face Region",
        description="",
        get=get_region_name,
        set=set_region_name,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_region_from_collection(self):
        region = utils.get_prop_from_collection(self.id_data, 'region')
        return region

    region_name_locked: bpy.props.StringProperty(
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

    permutation_name: bpy.props.StringProperty(
        name="Permutation",
        default="default",
        description="The permutation of this object. Permutations get exported to seperate files in scenario exports, or in model exports if the mesh type is one of render/collision/physics",
        get=get_permutation_name,
        set=set_permutation_name,
        override={'LIBRARY_OVERRIDABLE'},
    )

    def get_permutation_from_collection(self):
        permutation = utils.get_prop_from_collection(self.id_data, 'permutation')
        return permutation

    permutation_name_locked: bpy.props.StringProperty(
        name="Permutation",
        description="The permutation of this object. Leave blank for default",
        get=get_permutation_from_collection,
        override={'LIBRARY_OVERRIDABLE'},
    )

    is_pca: bpy.props.BoolProperty(
        name="Frame PCA",
        options=set(),
        description="",
        default=False,
    )
    
    export_collection: bpy.props.StringProperty(options={'HIDDEN'})
    
    invert_topology: bpy.props.BoolProperty(options={'HIDDEN'})
    
    # GETTER PROPS
    def get_object_id(self):
        current_id = self.get('object_id', 0)
        if current_id:
            return current_id
        
        rnd = random.Random()
        id = str(uuid.UUID(int=rnd.getrandbits(128)))
        self['object_id'] = id
        return id
    
    ObjectID: bpy.props.StringProperty(
        get=get_object_id,
    )

    # INSTANCED GEOMETRY ONLY

    instanced_collision: bpy.props.BoolProperty(
        name="Bullet Collision",
    )
    instanced_physics: bpy.props.BoolProperty(
        name="Player Collision",
    )

    cookie_cutter: bpy.props.BoolProperty(
        name="Cookie Cutter",
    )

    #########

    toggle_face_defaults: bpy.props.BoolProperty()

    # MARKER PERMS
    marker_exclude_permutations : bpy.props.StringProperty()
    marker_include_permutations : bpy.props.StringProperty()